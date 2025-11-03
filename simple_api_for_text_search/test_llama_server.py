"""
llama.cpp 서버 응답 형식 확인 스크립트
"""
import requests
import json

LLAMA_SERVER_URL = "http://localhost:8080"

print("=== llama.cpp 서버 테스트 ===\n")

# 1. 서버 상태 확인
print("1. 서버 상태 확인")
try:
    response = requests.get(f"{LLAMA_SERVER_URL}/health", timeout=5)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}\n")
except Exception as e:
    print(f"   Error: {e}\n")

# 2. 임베딩 요청 - content 방식
print("2. 임베딩 요청 (content)")
try:
    response = requests.post(
        f"{LLAMA_SERVER_URL}/embedding",
        json={"content": "테스트 문장입니다"},
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
except Exception as e:
    print(f"   Error: {e}\n")

# 3. 임베딩 요청 - prompt 방식
print("3. 임베딩 요청 (prompt)")
try:
    response = requests.post(
        f"{LLAMA_SERVER_URL}/embedding",
        json={"prompt": "테스트 문장입니다"},
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
except Exception as e:
    print(f"   Error: {e}\n")

# 4. 임베딩 요청 - input 방식
print("4. 임베딩 요청 (input)")
try:
    response = requests.post(
        f"{LLAMA_SERVER_URL}/embedding",
        json={"input": "테스트 문장입니다"},
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
except Exception as e:
    print(f"   Error: {e}\n")

# 5. v1/embeddings 엔드포인트 시도
print("5. OpenAI 호환 엔드포인트 (/v1/embeddings)")
try:
    response = requests.post(
        f"{LLAMA_SERVER_URL}/v1/embeddings",
        json={"input": "테스트 문장입니다"},
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
except Exception as e:
    print(f"   Error: {e}\n")
