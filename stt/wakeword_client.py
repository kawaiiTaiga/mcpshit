import openwakeword
from openwakeword.model import Model
import pyaudio
import numpy as np
from datetime import datetime
import time
import requests
import io

class WakeWordClient:
    def __init__(self, 
                 wakeword_model_path="ruby_chan.onnx",
                 whisper_server_url="http://localhost:8000",
                 webhook_url="http://localhost:9000/webhook",  # 추가
                 wakeword_threshold=0.5,
                 max_recording_duration=10.0,
                 silence_duration=1.5,
                 silence_threshold=500,
                 cooldown_time=3.0):
        """
        Wake Word 감지 + 녹음 클라이언트 (호스트 CPU에서 실행)
        Whisper는 Docker GPU 서버로 요청
        
        Args:
            whisper_server_url: Whisper API 서버 주소
            webhook_url: 이벤트 전송할 webhook URL
        """
        # Wake Word 모델 초기화 (CPU)
        print("Wake Word 모델 로딩 중... (CPU)")
        self.wakeword_model = Model(wakeword_models=[wakeword_model_path])
        
        self.whisper_server_url = whisper_server_url
        self.webhook_url = webhook_url
        self.wakeword_threshold = wakeword_threshold
        self.max_recording_duration = max_recording_duration
        self.silence_duration = silence_duration
        self.silence_threshold = silence_threshold
        self.cooldown_time = cooldown_time
        
        self.last_wakeword_time = 0
        
        # PyAudio 설정
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 1280
        
        self.audio = pyaudio.PyAudio()
        
        # 서버 연결 테스트
        self._test_server_connection()
        
        print("초기화 완료!")
    
    def _test_server_connection(self):
        """Whisper 서버 연결 테스트"""
        try:
            response = requests.get(f"{self.whisper_server_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Whisper 서버 연결 성공: {self.whisper_server_url}")
                print(f"   서버 상태: {response.json()}")
            else:
                print(f"⚠️  Whisper 서버 응답 이상: {response.status_code}")
        except Exception as e:
            print(f"❌ Whisper 서버 연결 실패: {e}")
            print(f"   서버 주소를 확인하세요: {self.whisper_server_url}")
    
    def send_wakeword_event(self, model_name, confidence):
        """Wake Word 감지 이벤트 전송"""
        try:
            payload = {
                "event_type": "wakeword_detected",
                "model_name": model_name,
                "confidence": float(confidence),  # numpy float32 -> Python float 변환
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"📤 Wake Word 이벤트 전송 성공")
            else:
                print(f"⚠️  Wake Word 이벤트 전송 실패: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Wake Word 이벤트 전송 에러: {e}")
    
    def send_transcription_result(self, text):
        """음성 인식 결과 전송"""
        try:
            payload = {
                "event_type": "transcription_result",
                "text": text,
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"📤 음성 인식 결과 전송 성공")
            else:
                print(f"⚠️  음성 인식 결과 전송 실패: {response.status_code}")
                
        except Exception as e:
            print(f"❌음성 인식 결과 전송 에러: {e}")
    
    def calculate_rms(self, audio_chunk):
        """오디오 청크의 RMS 계산"""
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(audio_array**2))
        return rms
    
    def record_audio_with_vad(self):
        """VAD를 사용한 스마트 녹음"""
        print(f"🎤 녹음 시작... (최대 {self.max_recording_duration}초, 무음 {self.silence_duration}초 시 종료)")
        
        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        frames = []
        silent_chunks = 0
        max_silent_chunks = int(self.silence_duration / (self.CHUNK / self.RATE))
        max_chunks = int(self.max_recording_duration / (self.CHUNK / self.RATE))
        
        recording_started = False
        
        for i in range(max_chunks):
            data = stream.read(self.CHUNK)
            frames.append(data)
            
            rms = self.calculate_rms(data)
            
            if rms > self.silence_threshold:
                silent_chunks = 0
                recording_started = True
            else:
                if recording_started:
                    silent_chunks += 1
            
            if recording_started and silent_chunks >= max_silent_chunks:
                actual_duration = (i + 1) * self.CHUNK / self.RATE
                print(f"✓ 녹음 완료 ({actual_duration:.1f}초 - 무음 감지)")
                break
        else:
            print(f"✓ 녹음 완료 ({self.max_recording_duration}초 - 최대 시간)")
        
        stream.stop_stream()
        stream.close()
        
        return b''.join(frames)
    
    def transcribe_via_server(self, audio_data):
        """Docker GPU 서버로 음성 데이터를 전송하여 텍스트로 변환"""
        print("🔄 Whisper 서버로 전송 중...")
        
        try:
            # 오디오 데이터를 파일처럼 전송
            files = {
                'audio': ('audio.raw', io.BytesIO(audio_data), 'application/octet-stream')
            }
            
            response = requests.post(
                f"{self.whisper_server_url}/transcribe",
                files=files,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['text']
            else:
                print(f"❌ 서버 에러: {response.status_code}")
                print(f"   응답: {response.text}")
                return ""
                
        except Exception as e:
            print(f"❌ 전송 실패: {e}")
            return ""
    
    def listen_for_wakeword(self):
        """Wake Word를 지속적으로 감지"""
        print("\n" + "="*60)
        print("🎧 마이크 리스닝 중...")
        print(f"   💻 Wake Word: CPU (로컬)")
        print(f"   🚀 Whisper: GPU (서버 {self.whisper_server_url})")
        print(f"   📡 Webhook: {self.webhook_url}")
        print(f"   Wake Word 임계값: {self.wakeword_threshold}")
        print(f"   최대 녹음 시간: {self.max_recording_duration}초")
        print(f"   무음 감지 시간: {self.silence_duration}초")
        print(f"   쿨다운 시간: {self.cooldown_time}초")
        print("="*60 + "\n")
        
        try:
            while True:
                # Wake Word 감지 스트림 열기
                stream = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK
                )
                
                wakeword_detected = False
                detected_model_name = None
                detected_confidence = 0.0
                
                # Wake Word 감지 루프
                while not wakeword_detected:
                    audio_data = np.frombuffer(stream.read(self.CHUNK), dtype=np.int16)
                    prediction = self.wakeword_model.predict(audio_data)
                    
                    for model_name, score in prediction.items():
                        if score > self.wakeword_threshold:
                            current_time = time.time()
                            time_since_last = current_time - self.last_wakeword_time
                            
                            if time_since_last < self.cooldown_time:
                                print(f"[DEBUG] 쿨다운 중 무시 (경과: {time_since_last:.2f}초, 신뢰도: {score:.3f})")
                                continue
                            
                            self.last_wakeword_time = current_time
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            print(f"\n[{timestamp}] ✨ Wake Word '{model_name}' 감지! (신뢰도: {score:.3f})")
                            
                            detected_model_name = model_name
                            detected_confidence = score
                            wakeword_detected = True
                            break
                
                # 스트림 종료
                stream.stop_stream()
                stream.close()
                
                # Wake Word 이벤트 전송
                self.send_wakeword_event(detected_model_name, detected_confidence)
                
                time.sleep(0.5)
                
                # 녹음 및 GPU 서버로 STT 요청
                audio_data = self.record_audio_with_vad()
                text = self.transcribe_via_server(audio_data)
                
                if text:
                    print(f"📝 인식된 텍스트: '{text}'")
                    # 음성 인식 결과 전송
                    self.send_transcription_result(text)
                else:
                    print("⚠️  음성이 인식되지 않았습니다.")
                
                self.last_wakeword_time = time.time()
                print(f"[DEBUG] 쿨다운 시작: {self.cooldown_time}초")
                print("\n🎧 다시 Wake Word 대기 중...\n")
                        
        except KeyboardInterrupt:
            print("\n\n종료 중...")
        finally:
            self.audio.terminate()
    
    def run(self):
        """클라이언트 실행"""
        self.listen_for_wakeword()


if __name__ == "__main__":
    # 클라이언트 설정 및 실행
    client = WakeWordClient(
        wakeword_model_path="ruby_chan.onnx",
        whisper_server_url="http://localhost:8000",  # Docker 서버 주소
        webhook_url="http://localhost:9000/webhook",  # Webhook 주소
        wakeword_threshold=0.5,
        max_recording_duration=10.0,
        silence_duration=1.5,
        silence_threshold=500,
        cooldown_time=3.0
    )
    
    client.run()