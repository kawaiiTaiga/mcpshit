"""
Fish TTS GUI 플레이어 - 독립 실행형
파일을 감시하면서 새로운 음성 파일을 자동으로 재생합니다.
"""
import tkinter as tk
from tkinter import ttk
import pygame
from pathlib import Path
import time
import sys

class AudioPlayer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎵 Fish TTS Player")
        self.root.geometry("450x300")
        self.root.configure(bg='#f0f0f0')
        
        # 음악 초기화
        pygame.mixer.init()
        
        # UI 구성
        main_frame = ttk.Frame(self.root, padding="30")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 타이틀
        title_label = ttk.Label(
            main_frame, 
            text="🎤 Fish TTS Audio Player", 
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, pady=10)
        
        # 상태 표시
        self.status_label = ttk.Label(
            main_frame, 
            text="⏸ 대기 중...", 
            font=("Arial", 12)
        )
        self.status_label.grid(row=1, column=0, pady=10)
        
        # 텍스트 표시
        self.text_label = ttk.Label(
            main_frame, 
            text="", 
            wraplength=380, 
            font=("Arial", 10),
            justify='center'
        )
        self.text_label.grid(row=2, column=0, pady=10)
        
        # 파일명 표시
        self.file_label = ttk.Label(
            main_frame, 
            text="", 
            font=("Arial", 9), 
            foreground="gray"
        )
        self.file_label.grid(row=3, column=0, pady=5)
        
        # 재생 횟수
        self.count_label = ttk.Label(
            main_frame,
            text="재생 횟수: 0",
            font=("Arial", 9),
            foreground="blue"
        )
        self.count_label.grid(row=4, column=0, pady=5)
        
        # 종료 버튼
        self.quit_button = ttk.Button(
            main_frame, 
            text="❌ 종료", 
            command=self.on_close
        )
        self.quit_button.grid(row=5, column=0, pady=20)
        
        # 통계
        self.play_count = 0
        self.played_files = set()
        
        # 폴더 생성
        self.output_dir = Path("C:/Users/gaterbelt/Downloads/speak_mcp/tts_output")

        self.output_dir.mkdir(exist_ok=True)
        
        # 파일 감시 시작
        self.watch_folder()
        
        # 창 닫기 이벤트
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def watch_folder(self):
        """폴더를 감시하고 새 파일이 생기면 재생"""
        def check_new_files():
            try:
                files = sorted(self.output_dir.glob("speech_*.wav"))
                
                for file in files:
                    if file not in self.played_files:
                        self.played_files.add(file)
                        self.play_audio(file)
                        
            except Exception as e:
                self.status_label.config(text=f"⚠️ 오류: {e}")
            
            # 500ms마다 체크
            self.root.after(500, check_new_files)
        
        check_new_files()
    
    def play_audio(self, filepath):
        """오디오 파일 재생"""
        try:
            self.status_label.config(text="▶️ 재생 중...")
            self.file_label.config(text=f"파일: {filepath.name}")
            
            # 파일명에서 텍스트 추출 시도 (선택사항)
            self.text_label.config(text="🎵 음성 재생 중...")
            
            # 음악 로드 및 재생
            pygame.mixer.music.load(str(filepath))
            pygame.mixer.music.play()
            
            # 재생 완료 대기
            while pygame.mixer.music.get_busy():
                self.root.update()
                time.sleep(0.1)
            
            self.play_count += 1
            self.count_label.config(text=f"재생 횟수: {self.play_count}")
            self.status_label.config(text="✅ 재생 완료!")
            
            # 2초 후 대기 상태로
            self.root.after(2000, lambda: self.status_label.config(text="⏸ 대기 중..."))
            
        except Exception as e:
            self.status_label.config(text=f"❌ 재생 오류: {e}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    def on_close(self):
        """종료 처리"""
        try:
            pygame.mixer.quit()
        except:
            pass
        self.root.destroy()
        sys.exit(0)
    
    def run(self):
        """메인 루프 실행"""
        try:
            print("🎵 Fish TTS Player 시작")
            print(f"📁 감시 폴더: {self.output_dir.absolute()}")
            print("✨ 새로운 음성 파일을 기다리는 중...")
            self.root.mainloop()
        except Exception as e:
            print(f"GUI Error: {e}")
            import traceback
            traceback.print_exc()
            input("Press Enter to close...")

if __name__ == "__main__":
    try:
        player = AudioPlayer()
        player.run()
    except Exception as e:
        print(f"Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to close...")