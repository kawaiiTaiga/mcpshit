import openwakeword
from openwakeword.model import Model
import pyaudio
import numpy as np
from datetime import datetime
import time
import requests
import io
import threading
import os
import pygame
import pyautogui
import pyperclip
import wave

# Status Constants
STATUS_IDLE = "idle"           # Sleeping
STATUS_LISTENING = "listening" # Waiting for wakeword
STATUS_WAKED = "waked"         # Wakeword detected
STATUS_RECORDING = "recording" # Recording voice
STATUS_PROCESSING = "processing" # Sending to Whisper
STATUS_TYPED = "typed"         # Text typed

class WakeWordClient:
    def __init__(self, 
                 wakeword_models=["ruby_chan.onnx"],
                 whisper_server_url="http://localhost:8000",
                 wakeword_threshold=0.5,
                 max_recording_duration=10.0,
                 silence_duration=1.5,
                 silence_threshold=500,
                 cooldown_time=3.0,
                 overlay_image_path="overlay.png",
                 overlay_duration_ms=1500,
                 overlay_sound_file=None,
                 log_callback=None,
                 on_wakeword=None,
                 status_callback=None
                 ):
        """
        Wake Word 감지 + 녹음 클라이언트
        """
        self.log_callback = log_callback
        self.on_wakeword = on_wakeword
        self.status_callback = status_callback
        self.log("Wake Word 모델 로딩 중... (CPU)")
        
        # 모델 경로 확인 및 로드
        valid_models = []
        for model in wakeword_models:
            if os.path.exists(model):
                valid_models.append(model)
            else:
                self.log(f"⚠️ 모델 파일을 찾을 수 없습니다: {model}")
        
        if not valid_models:
            self.log("❌ 유효한 모델이 없습니다. 기본 모델을 확인해주세요.")
        
        self.wakeword_model = Model(wakeword_models=valid_models)
        
        self.whisper_server_url = whisper_server_url
        self.wakeword_threshold = wakeword_threshold
        self.max_recording_duration = max_recording_duration
        self.silence_duration = silence_duration
        self.silence_threshold = silence_threshold
        self.cooldown_time = cooldown_time
        
        self.overlay_image_path = overlay_image_path
        self.overlay_duration_ms = overlay_duration_ms
        self.overlay_sound_file = overlay_sound_file
        
        self.last_wakeword_time = 0
        self.running = False
        
        # PyAudio 설정
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 1280
        
        self.audio = None # 초기화 지연
        
        self._test_server_connection()
        self.log("초기화 완료!")

    def log(self, message):
        print(message)
        if self.log_callback:
            self.log_callback(message)

    def update_status(self, status):
        if self.status_callback:
            self.status_callback(status)

    def stop(self):
        self.running = False
        self.update_status(STATUS_IDLE)

    def _test_server_connection(self):
        try:
            response = requests.get(f"{self.whisper_server_url}/health", timeout=5)
            if response.status_code == 200:
                self.log(f"✅ Whisper 서버 연결 성공: {self.whisper_server_url}")
            else:
                self.log(f"⚠️  Whisper 서버 응답 이상: {response.status_code}")
        except Exception as e:
            self.log(f"❌ Whisper 서버 연결 실패: {e}")

    def type_text_and_enter(self, text):
        """텍스트 입력 및 엔터"""
        try:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            pyautogui.press('enter')
            self.log(f"✅ 텍스트 입력 완료: '{text}'")
            self.update_status(STATUS_TYPED)
        except Exception as e:
            self.log(f"❌ 텍스트 입력 에러: {e}")
    
    def play_sound(self):
        if self.overlay_sound_file and os.path.exists(self.overlay_sound_file):
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(self.overlay_sound_file)
                pygame.mixer.music.play()
            except Exception as e:
                self.log(f"❌ 사운드 에러: {e}")

    def calculate_rms(self, audio_chunk):
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(audio_array**2))
        return rms
    
    def record_audio_with_vad(self):
        self.update_status(STATUS_RECORDING)
        self.log(f"🎤 녹음 시작... (최대 {self.max_recording_duration}초)")
        
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
            if not self.running: break
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
                break
        
        stream.stop_stream()
        stream.close()
        
        return b''.join(frames)
    
    def transcribe_via_server(self, audio_data):
        self.update_status(STATUS_PROCESSING)
        self.log("🔄 Whisper 서버로 전송 중...")
        try:
            files = {'audio': ('audio.raw', io.BytesIO(audio_data), 'application/octet-stream')}
            response = requests.post(
                f"{self.whisper_server_url}/transcribe",
                files=files,
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                return result.get('text', '')
            else:
                self.log(f"❌ 서버 에러: {response.status_code}")
                return ""
        except Exception as e:
            self.log(f"❌ 전송 실패: {e}")
            return ""
    
    def run(self):
        self.running = True
        self.update_status(STATUS_LISTENING)
        self.log("\n" + "="*60)
        self.log("🎧 마이크 리스닝 중...")
        self.log("="*60 + "\n")
        
        try:
            self.audio = pyaudio.PyAudio()
            
            while self.running:
                stream = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK
                )
                
                wakeword_detected = False
                
                while not wakeword_detected and self.running:
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    # 쿨다운 체크 (루프 시작 시)
                    if time.time() - self.last_wakeword_time < self.cooldown_time:
                        continue

                    prediction = self.wakeword_model.predict(audio_data)
                    
                    for model_name, score in prediction.items():
                        if score > self.wakeword_threshold:
                            self.log(f"✨ Wake Word '{model_name}' 감지! ({score:.3f})")
                            self.update_status(STATUS_WAKED)
                            
                            # 1. 콜백 호출 (GUI 오버레이용)
                            if self.on_wakeword:
                                self.on_wakeword()
                            
                            # 2. 사운드 재생
                            threading.Thread(target=self.play_sound, daemon=True).start()
                            
                            wakeword_detected = True
                            break
                
                stream.stop_stream()
                stream.close()
                
                if not self.running: break

                if wakeword_detected:
                    # 모델 상태 리셋 (중복 감지 방지)
                    self.wakeword_model.reset()
                    
                    audio_data = self.record_audio_with_vad()
                    text = self.transcribe_via_server(audio_data)
                    
                    if text:
                        self.log(f"📝 인식된 텍스트: '{text}'")
                        threading.Thread(target=self.type_text_and_enter, args=(text,), daemon=True).start()
                    else:
                        self.log("⚠️  음성이 인식되지 않았습니다.")
                    
                    # 쿨다운 시작 (모든 작업 완료 후)
                    self.last_wakeword_time = time.time()
                    self.log(f"쿨다운 시작: {self.cooldown_time}초")
                    time.sleep(self.cooldown_time)
                    self.update_status(STATUS_LISTENING)
                    self.log("🎧 다시 대기 중...")
                        
        except Exception as e:
            self.log(f"Error in run loop: {e}")
        finally:
            if self.audio:
                self.audio.terminate()
                self.audio = None
            try:
                pygame.mixer.quit()
            except:
                pass

if __name__ == "__main__":
    client = WakeWordClient()
    client.run()