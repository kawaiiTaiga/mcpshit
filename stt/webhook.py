from fastapi import FastAPI, Request
import pyaudio
import wave
import pyautogui
import pyperclip
import threading
from datetime import datetime

app = FastAPI()

# 설정
WAKEWORD_SOUND_PATH = "wakeword_sound.wav"  # Wake Word 감지 시 재생할 사운드 파일


def play_sound(wav_file_path):
    """WAV 파일 재생 (별도 쓰레드에서 실행)"""
    try:
        # WAV 파일 열기
        wf = wave.open(wav_file_path, 'rb')
        
        # PyAudio 인스턴스 생성
        p = pyaudio.PyAudio()
        
        # 스트림 열기
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )
        
        # 데이터 읽고 재생
        chunk = 1024
        data = wf.readframes(chunk)
        
        while data:
            stream.write(data)
            data = wf.readframes(chunk)
        
        # 정리
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf.close()
        
        print(f"✅ 사운드 재생 완료: {wav_file_path}")
        
    except FileNotFoundError:
        print(f"❌ 사운드 파일을 찾을 수 없습니다: {wav_file_path}")
    except Exception as e:
        print(f"❌ 사운드 재생 에러: {e}")


def type_text_and_enter(text):
    """클립보드를 사용하여 텍스트 입력하고 엔터 누르기 (한글 지원)"""
    try:
        # 클립보드에 텍스트 복사
        pyperclip.copy(text)
        
        # Ctrl+V로 붙여넣기
        pyautogui.hotkey('ctrl', 'v')
        
        # 잠깐 대기 (붙여넣기 완료 대기)
        import time
        time.sleep(0.1)
        
        # 엔터 누르기
        pyautogui.press('enter')
        
        print(f"✅ 텍스트 입력 완료: '{text}'")
        
    except Exception as e:
        print(f"❌ 텍스트 입력 에러: {e}")


@app.post("/webhook")
async def webhook_handler(request: Request):
    """Webhook 이벤트 핸들러"""
    try:
        data = await request.json()
        event_type = data.get("event_type")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if event_type == "wakeword_detected":
            # Wake Word 감지 이벤트
            model_name = data.get("model_name")
            confidence = data.get("confidence")
            
            print(f"\n[{timestamp}] 🔔 Wake Word 이벤트 수신")
            print(f"   모델: {model_name}")
            print(f"   신뢰도: {confidence:.3f}")
            
            # 사운드 재생 (별도 쓰레드에서 실행하여 블로킹 방지)
            thread = threading.Thread(target=play_sound, args=(WAKEWORD_SOUND_PATH,))
            thread.daemon = True
            thread.start()
            
        elif event_type == "transcription_result":
            # 음성 인식 결과 이벤트
            text = data.get("text")
            
            print(f"\n[{timestamp}] 📝 음성 인식 결과 수신")
            print(f"   텍스트: '{text}'")
            
            # 키보드 매크로 실행 (별도 쓰레드)
            thread = threading.Thread(target=type_text_and_enter, args=(text,))
            thread.daemon = True
            thread.start()
            
        else:
            print(f"\n[{timestamp}] ⚠️  알 수 없는 이벤트 타입: {event_type}")
        
        return {"status": "success", "event_type": event_type}
        
    except Exception as e:
        print(f"❌ Webhook 처리 에러: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "ok",
        "wakeword_sound": WAKEWORD_SOUND_PATH
    }


if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🚀 Webhook 서버 시작")
    print(f"   포트: 9000")
    print(f"   Wake Word 사운드: {WAKEWORD_SOUND_PATH}")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=9000)