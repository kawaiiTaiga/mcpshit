# Milvus Lite Vector Search API

BGE-M3-KO 임베딩 모델과 Milvus Lite를 사용한 간단한 벡터 검색 API...
mcp는 아니고 mcp 만들기 편할려고 만들어둠

## 설치 및 실행

### 1. 프로젝트 구조
```
milvus-api/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── app.py
├── models/
│   └── bge-m3-ko.gguf  # 여기에 모델 파일을 넣으세요
└── milvus_data/         # 자동 생성됨
```

### 2. 모델 파일 준비
`models/` 폴더를 만들고 `bge-m3-ko.gguf` 파일을 넣어주세요.

```bash
mkdir -p models
# bge-m3-ko.gguf 파일을 models/ 폴더에 복사
```

### 3. 도커 실행
```bash
docker-compose up -d
```

### 4. API 확인
브라우저에서 접속: http://localhost:8000

자동 API 문서: http://localhost:8000/docs

## API 사용법

### 1. 데이터 삽입
```bash
curl -X POST "http://localhost:8000/insert" \
  -H "Content-Type: application/json" \
  -d '{
    "db_name": "my_database",
    "content": "이것은 테스트 문서입니다",
    "metadata": {"source": "test", "date": "2025-11-03"}
  }'
```

**응답:**
```json
{
  "status": "success",
  "message": "데이터가 'my_database'에 저장되었습니다",
  "insert_count": 1,
  "ids": [450345334563456345]
}
```

### 2. 유사도 검색
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "db_name": "my_database",
    "query": "테스트",
    "k": 5
  }'
```

**응답:**
```json
[
  {
    "content": "이것은 테스트 문서입니다",
    "score": 0.95,
    "metadata": {"source": "test", "date": "2025-11-03"}
  }
]
```

### 3. 컬렉션 목록 조회
```bash
curl -X GET "http://localhost:8000/collections"
```

### 4. 컬렉션 삭제
```bash
curl -X DELETE "http://localhost:8000/collections/my_database"
```

## Python 예제

```python
import requests

# 1. 데이터 삽입
response = requests.post(
    "http://localhost:8000/insert",
    json={
        "db_name": "knowledge_base",
        "content": "FastAPI는 Python으로 만든 웹 프레임워크입니다",
        "metadata": {"category": "programming"}
    }
)
print(response.json())

# 2. 검색
response = requests.post(
    "http://localhost:8000/search",
    json={
        "db_name": "knowledge_base",
        "query": "파이썬 웹 프레임워크",
        "k": 3
    }
)
results = response.json()
for result in results:
    print(f"점수: {result['score']:.2f} - {result['content']}")
```

## 로그 확인

```bash
# 전체 로그
docker-compose logs -f

# FastAPI 로그만
docker-compose logs -f fastapi-app

# llama.cpp 로그만
docker-compose logs -f llama-server
```

## 중지 및 삭제

```bash
# 중지
docker-compose stop

# 완전 삭제 (데이터 보존)
docker-compose down

# 데이터까지 삭제
docker-compose down -v
rm -rf milvus_data/
```

## 문제 해결

### llama.cpp 서버가 시작되지 않는 경우
- `models/bge-m3-ko.gguf` 파일이 올바른 위치에 있는지 확인
- 로그 확인: `docker-compose logs llama-server`

### 임베딩 생성 오류
- llama.cpp 서버가 실행 중인지 확인: `curl http://localhost:8080/health`
- 모델이 임베딩 모드를 지원하는지 확인

### Milvus 오류
- `milvus_data/` 폴더 권한 확인
- 데이터 초기화: `rm -rf milvus_data/` 후 재시작
