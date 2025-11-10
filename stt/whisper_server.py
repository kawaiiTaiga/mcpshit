from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
import numpy as np
import io
import uvicorn
from pydantic import BaseModel

app = FastAPI(title="Faster-Whisper GPU Server")

# GPU에서 Whisper 모델 로드
print("🚀 Faster-Whisper 모델 로딩 중... (GPU)")
whisper_model = WhisperModel(
    "medium",  # tiny, base, small, medium, large
    device="cuda",
    compute_type="float16"
)
print("✅ 모델 로딩 완료!")


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    segments: list


@app.get("/")
async def root():
    return {"status": "online", "message": "Faster-Whisper GPU Server"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "device": "cuda"}


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    오디오 파일을 받아서 텍스트로 변환
    """
    try:
        # 오디오 데이터 읽기
        audio_bytes = await audio.read()
        
        # bytes를 numpy 배열로 변환 (16-bit PCM -> float32)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        print(f"🎤 오디오 수신: {len(audio_bytes)} bytes")
        
        # Whisper 실행
        segments, info = whisper_model.transcribe(
            audio_np,
            language="ko",
            beam_size=5,
            vad_filter=True,
        )
        
        # 세그먼트 정보 수집
        segment_list = []
        full_text = []
        
        for segment in segments:
            segment_list.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text
            })
            full_text.append(segment.text)
        
        result_text = " ".join(full_text).strip()
        
        print(f"📝 인식 결과: '{result_text}'")
        
        return TranscriptionResponse(
            text=result_text,
            language=info.language,
            segments=segment_list
        )
        
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
