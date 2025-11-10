# 🚀 빠른 시작 가이드

## 1단계: Docker GPU 서버 띄우기

```bash
# 이 디렉토리에서 실행
docker-compose up -d --build

# 서버가 준비될 때까지 잠시 대기 (1-2분)
# 로그 확인
docker-compose logs -f
```

서버가 제대로 떴는지 확인:
```bash
curl http://localhost:8000/health
```

응답이 `{"status":"healthy","device":"cuda"}` 이면 성공!

## 2단계: 호스트에서 클라이언트 실행

**Windows에서:**
```cmd
# 필요한 패키지 설치 (처음 한 번만)
pip install openwakeword pyaudio numpy requests

# Wake Word 모델 경로 수정 후 실행
python wakeword_client.py
```

**실행되면 이렇게 보입니다:**
```
Wake Word 모델 로딩 중... (CPU)
✅ Whisper 서버 연결 성공: http://localhost:8000
   서버 상태: {'status': 'healthy', 'device': 'cuda'}
초기화 완료!

============================================================
🎧 마이크 리스닝 중...
   💻 Wake Word: CPU (로컬)
   🚀 Whisper: GPU (서버 http://localhost:8000)
   Wake Word 임계값: 0.5
   최대 녹음 시간: 10.0초
   무음 감지 시간: 1.5초
   쿨다운 시간: 3.0초
============================================================
```

## 3단계: 테스트

1. Wake Word를 말하세요 (예: "루비짱")
2. Wake Word가 감지되면 자동으로 녹음 시작
3. 명령을 말하세요 (예: "불 좀 켜줘")
4. 1.5초 무음 후 자동으로 녹음 종료
5. GPU 서버에서 텍스트로 변환
6. 결과 출력!

## 트러블슈팅

### "Whisper 서버 연결 실패"
```bash
# Docker 컨테이너 확인
docker ps

# 로그 확인
docker-compose logs
```

### "PyAudio 설치 오류" (Windows)
```cmd
pip install pipwin
pipwin install pyaudio
```

### GPU 미인식
```bash
# NVIDIA GPU 확인
nvidia-smi

# Docker에서 GPU 확인
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

## 중지하기

```bash
# Docker 서버 중지
docker-compose down

# 클라이언트는 Ctrl+C로 종료
```

## 다음 단계

- `wakeword_client.py`에서 임계값 조정
- `whisper_server.py`에서 Whisper 모델 크기 변경 (tiny/base/small/medium/large)
- 여러 개의 클라이언트로 동시 사용 테스트
