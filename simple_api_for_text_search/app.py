from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import requests
import os
import json
from pymilvus import MilvusClient


def _to_json_ids(ids_raw):
    """Milvus가 반환한 id 리스트를 JSON 직렬화 가능한 기본형으로 변환"""
    out = []
    for x in (ids_raw or []):
        try:
            # numpy.int64 등도 int()로 캐스팅
            out.append(int(x))
        except Exception:
            # 혹시 캐스팅 실패하면 문자열로라도 반환
            out.append(str(x))
    return out
app = FastAPI(title="Milvus Lite Vector Search API")

# 환경 변수
LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://localhost:8080")
MILVUS_DB_DIR = "./milvus_data"

# Milvus 데이터 디렉토리 생성
os.makedirs(MILVUS_DB_DIR, exist_ok=True)

# Milvus 클라이언트 (lazy initialization)
_milvus_client = None

def get_milvus_client():
    """Milvus 클라이언트 가져오기 (싱글톤)"""
    global _milvus_client
    if _milvus_client is None:
        # Milvus Lite 초기화
        db_file = os.path.join(MILVUS_DB_DIR, "milvus_demo.db")
        _milvus_client = MilvusClient(db_file)
    return _milvus_client


# Request/Response 모델
class InsertRequest(BaseModel):
    db_name: str
    content: str
    metadata: Optional[dict] = None


class SearchRequest(BaseModel):
    db_name: str
    query: str
    k: int = 5


class SearchResult(BaseModel):
    content: str
    score: float
    metadata: Optional[dict] = None


# 임베딩 생성 함수 (다양한 응답 포맷을 안전하게 처리)
def get_embedding(text: str) -> List[float]:
    """llama.cpp 서버에서 임베딩 생성"""
    try:
        response = requests.post(
            f"{LLAMA_SERVER_URL}/embedding",
            json={"content": text},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        embedding = None

        # 1) 최상위가 dict
        if isinstance(result, dict):
            if "embedding" in result:
                embedding = result["embedding"]
            elif "data" in result and isinstance(result["data"], list) and result["data"]:
                item = result["data"][0]
                if isinstance(item, dict) and "embedding" in item:
                    embedding = item["embedding"]

        # 2) 최상위가 list (예: [{"index":0,"embedding":[...]}] 또는 [[...]])
        if embedding is None and isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict) and "embedding" in first:
                embedding = first["embedding"]
            elif isinstance(first, list):
                embedding = first

        # 3) 2차원([[...]] )이면 첫 벡터만 사용
        if isinstance(embedding, list) and embedding and isinstance(embedding[0], list):
            embedding = embedding[0]

        # 기본 검증
        if not isinstance(embedding, list) or not embedding or not all(isinstance(x, (int, float)) for x in embedding):
            raise ValueError(f"임베딩 응답 형식 오류: {result}")

        return embedding

    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail=f"llama.cpp 서버에 연결할 수 없습니다: {LLAMA_SERVER_URL}"
        )
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="임베딩 생성 시간 초과 (30초)")
    except requests.exceptions.HTTPError:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"llama.cpp 서버 오류 (status {response.status_code}): {response.text}"
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"임베딩 생성 실패: {type(e).__name__}: {str(e)}")


# 컬렉션 생성 또는 가져오기
def ensure_collection(collection_name: str, dimension: int = 1024):
    """컬렉션이 없으면 생성 (auto_id, 동적 필드 활성화)"""
    client = get_milvus_client()
    if not client.has_collection(collection_name):
        client.create_collection(
            collection_name=collection_name,
            dimension=dimension,
            auto_id=True,                 # PK 자동 생성
            primary_field="id",
            id_type="int",                # MilvusClient: "int" or "str"
            enable_dynamic_field=True,    # content, metadata 등 임의 필드 허용
            metric_type="COSINE",
        )


@app.get("/")
def root():
    """API 상태 확인"""
    return {
        "status": "running",
        "message": "Milvus Lite Vector Search API",
        "endpoints": {
            "insert": "POST /insert",
            "search": "POST /search",
            "collections": "GET /collections",
            "health": "GET /health"
        }
    }


@app.get("/health")
def health_check():
    """전체 시스템 헬스체크"""
    health_status = {
        "api": "ok",
        "llama_server": "unknown",
        "milvus": "unknown"
    }

    # llama.cpp 서버 체크
    try:
        resp = requests.get(f"{LLAMA_SERVER_URL}/health", timeout=5)
        if resp.status_code == 200:
            health_status["llama_server"] = "ok"
        else:
            health_status["llama_server"] = f"error: status {resp.status_code}"
    except Exception as e:
        health_status["llama_server"] = f"error: {str(e)}"

    # Milvus 체크
    try:
        client = get_milvus_client()
        client.list_collections()
        health_status["milvus"] = "ok"
    except Exception as e:
        health_status["milvus"] = f"error: {str(e)}"

    # 전체 상태 판단
    all_ok = all(v == "ok" for v in health_status.values())

    return {
        "status": "healthy" if all_ok else "unhealthy",
        "services": health_status
    }


@app.post("/insert")
def insert_data(request: InsertRequest):
    """
    데이터 삽입
    - db_name: 컬렉션 이름
    - content: 저장할 텍스트 내용
    - metadata: 추가 메타데이터 (선택, dict)
    """
    try:
        client = get_milvus_client()

        # 임베딩 생성
        embedding = get_embedding(request.content)
        if not embedding or len(embedding) == 0:
            raise ValueError("임베딩 벡터가 비어있습니다")

        # 컬렉션 확인/생성 (차원 동기화)
        ensure_collection(request.db_name, dimension=len(embedding))

        # 데이터 준비 (id는 자동 생성, metadata는 JSON으로 그대로)
        data = [{
            "vector": embedding,
            "content": request.content,
            "metadata": request.metadata or {}
        }]

        # 삽입
        result = client.insert(
            collection_name=request.db_name,
            data=data
        )

        ids_raw = None
        if isinstance(result, dict) and "ids" in result:
            ids_raw = result.get("ids")
        elif isinstance(result, list):
            ids_raw = result
        else:
            ids_raw = [result]

        ids = _to_json_ids(ids_raw)

        return {
            "status": "success",
            "message": f"데이터가 '{request.db_name}'에 저장되었습니다",
            "insert_count": len(ids),
            "ids": ids,
            "embedding_dimension": len(embedding)
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=f"삽입 실패: {error_detail}")


@app.post("/search", response_model=List[SearchResult])
def search_data(request: SearchRequest):
    """
    유사도 검색
    - db_name: 검색할 컬렉션 이름
    - query: 검색 쿼리
    - k: 반환할 결과 개수 (기본값: 5)
    """
    try:
        client = get_milvus_client()

        # 컬렉션 존재 확인
        if not client.has_collection(request.db_name):
            raise HTTPException(
                status_code=404,
                detail=f"컬렉션 '{request.db_name}'을 찾을 수 없습니다"
            )

        # 쿼리 임베딩 생성
        query_embedding = get_embedding(request.query)

        # 검색
        results = client.search(
            collection_name=request.db_name,
            data=[query_embedding],
            limit=request.k,
            output_fields=["content", "metadata"]
        )

        # 결과 포맷팅
        formatted_results = []
        for hit in results[0]:
            entity = hit.get("entity", {}) if isinstance(hit, dict) else getattr(hit, "entity", {})
            content = entity.get("content", "")
            metadata = entity.get("metadata", None)  # JSON 그대로

            distance = 0.0
            if isinstance(hit, dict):
                distance = float(hit.get("distance", 0.0))
            else:
                try:
                    distance = float(getattr(hit, "distance", 0.0))
                except Exception:
                    distance = 0.0

            result = SearchResult(
                content=content,
                score=distance,
                metadata=metadata if isinstance(metadata, dict) else None
            )
            formatted_results.append(result)

        return formatted_results

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")


@app.get("/collections")
def list_collections():
    """모든 컬렉션 목록 조회"""
    try:
        client = get_milvus_client()
        collections = client.list_collections()
        return {
            "collections": collections,
            "count": len(collections)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컬렉션 조회 실패: {str(e)}")


@app.delete("/collections/{collection_name}")
def delete_collection(collection_name: str):
    """컬렉션 삭제"""
    try:
        client = get_milvus_client()

        if not client.has_collection(collection_name):
            raise HTTPException(
                status_code=404,
                detail=f"컬렉션 '{collection_name}'을 찾을 수 없습니다"
            )

        client.drop_collection(collection_name)
        return {
            "status": "success",
            "message": f"컬렉션 '{collection_name}'이 삭제되었습니다"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"삭제 실패: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
