FROM nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 기본 패키지 설치
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# Python 패키지 설치
RUN pip3 install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    faster-whisper \
    numpy \
    python-multipart

# 서버 코드 복사
COPY whisper_server.py /app/

# 포트 노출
EXPOSE 8000

# 서버 실행
CMD ["python3", "whisper_server.py"]