"""
Milvus API 테스트 스크립트
Windows에서 실행: python test_api.py
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_insert():
    """데이터 삽입 테스트"""
    print("\n=== 데이터 삽입 테스트 ===")
    
    data = {
        "db_name": "test_db",
        "content": "FastAPI는 Python으로 만든 웹 프레임워크입니다",
        "metadata": {
            "category": "programming",
            "language": "ko"
        }
    }
    
    response = requests.post(f"{BASE_URL}/insert", json=data)
    print(f"상태 코드: {response.status_code}")
    print(f"응답: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    # 추가 데이터 삽입
    data2 = {
        "db_name": "test_db",
        "content": "Milvus는 벡터 데이터베이스입니다",
        "metadata": {"category": "database"}
    }
    requests.post(f"{BASE_URL}/insert", json=data2)
    
    data3 = {
        "db_name": "test_db",
        "content": "Docker는 컨테이너 기반 가상화 플랫폼입니다",
        "metadata": {"category": "devops"}
    }
    requests.post(f"{BASE_URL}/insert", json=data3)
    
    print("✅ 3개의 데이터 삽입 완료")


def test_search():
    """검색 테스트"""
    print("\n=== 검색 테스트 ===")
    
    queries = [
        "파이썬 웹 프레임워크",
        "데이터베이스",
        "컨테이너 가상화"
    ]
    
    for query in queries:
        print(f"\n검색어: '{query}'")
        data = {
            "db_name": "test_db",
            "query": query,
            "k": 3
        }
        
        response = requests.post(f"{BASE_URL}/search", json=data)
        
        if response.status_code == 200:
            results = response.json()
            for i, result in enumerate(results, 1):
                print(f"{i}. 점수: {result['score']:.4f} - {result['content']}")
        else:
            print(f"❌ 검색 실패: {response.text}")


def test_collections():
    """컬렉션 목록 조회 테스트"""
    print("\n=== 컬렉션 목록 조회 ===")
    
    response = requests.get(f"{BASE_URL}/collections")
    print(f"상태 코드: {response.status_code}")
    print(f"응답: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")


def test_health():
    """API 상태 확인"""
    print("\n=== API 상태 확인 ===")
    
    try:
        response = requests.get(BASE_URL)
        print(f"✅ API 정상 작동")
        print(f"응답: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return True
    except Exception as e:
        print(f"❌ API 연결 실패: {e}")
        print("Docker 컨테이너가 실행 중인지 확인하세요: docker-compose ps")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Milvus API 테스트 시작")
    print("=" * 50)
    
    # API 상태 확인
    if not test_health():
        exit(1)
    
    # 데이터 삽입 테스트
    test_insert()
    
    # 검색 테스트
    test_search()
    
    # 컬렉션 목록 조회
    test_collections()
    
    print("\n" + "=" * 50)
    print("✅ 모든 테스트 완료!")
    print("=" * 50)
    print("\n💡 FastAPI 문서: http://localhost:8000/docs")
