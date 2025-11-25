"""
Fish TTS Audio Player - Enhanced Visualization
"""
import tkinter as tk
from tkinter import ttk
import asyncio
import threading
import json
import queue
import time
import numpy as np
import pyaudio
from aiohttp import web
import requests
from collections import deque

# Configuration
HTTP_PORT = 5000
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

class AudioPlayerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎵 Fish TTS Player")
        self.root.geometry("600x500")
        self.root.configure(bg='#0a0e27')  # Deep blue dark mode
        
        self.audio_queue = queue.Queue()
        self.signal_target_url = None
        self.is_playing = False
        
        # Signal history for smoother visualization
        self.signal_history = deque(maxlen=50)
        self.current_signal = 0.0
        self.current_rms = 0.0
        
        self.setup_ui()
        self.start_server_thread()
        self.start_audio_thread()
        
        # Periodic UI update
        self.root.after(30, self.update_ui)

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#0a0e27")
        style.configure("TLabel", background="#0a0e27", foreground="#ffffff", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 20, "bold"), foreground="#5dfdcb")
        style.configure("Status.TLabel", font=("Segoe UI", 11), foreground="#a0b9d8")
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header with icon
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(pady=10)
        ttk.Label(header_frame, text="🎧 Audio Visualizer", style="Header.TLabel").pack()
        
        # Status
        self.status_var = tk.StringVar(value="🎵 Ready - Waiting for audio...")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, style="Status.TLabel")
        status_label.pack(pady=10)
        
        # === Waveform Visualization ===
        viz_frame = ttk.Frame(main_frame)
        viz_frame.pack(pady=20, fill=tk.BOTH, expand=True)
        
        # Waveform canvas (wider, shorter)
        self.wave_height = 120
        self.wave_width = 550
        self.wave_canvas = tk.Canvas(viz_frame, width=self.wave_width, height=self.wave_height, 
                                     bg="#162447", highlightthickness=2, highlightbackground="#1f4068")
        self.wave_canvas.pack()
        
        # Initialize waveform bars
        self.num_bars = 40
        self.bar_width = self.wave_width // self.num_bars - 2
        self.bars = []
        
        for i in range(self.num_bars):
            x1 = i * (self.bar_width + 2) + 5
            x2 = x1 + self.bar_width
            y1 = self.wave_height // 2
            y2 = self.wave_height // 2
            
            bar = self.wave_canvas.create_rectangle(
                x1, y1, x2, y2,
                fill="#5dfdcb", outline=""
            )
            self.bars.append(bar)
        
        # Center line
        self.wave_canvas.create_line(
            0, self.wave_height // 2, 
            self.wave_width, self.wave_height // 2,
            fill="#1f4068", width=1
        )
        
        # === Volume Meter ===
        meter_frame = ttk.Frame(main_frame)
        meter_frame.pack(pady=10)
        
        ttk.Label(meter_frame, text="Volume", font=("Segoe UI", 9), foreground="#7d8da1").pack()
        
        self.meter_canvas = tk.Canvas(meter_frame, width=400, height=30, 
                                     bg="#162447", highlightthickness=1, highlightbackground="#1f4068")
        self.meter_canvas.pack(pady=5)
        
        # Volume bar
        self.volume_bar = self.meter_canvas.create_rectangle(
            2, 2, 2, 28,
            fill="#5dfdcb", outline=""
        )
        
        # Volume percentage
        self.volume_var = tk.StringVar(value="0%")
        ttk.Label(meter_frame, textvariable=self.volume_var, 
                 font=("Segoe UI", 9, "bold"), foreground="#5dfdcb").pack()
        
        # === Info Panel ===
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(side=tk.BOTTOM, pady=10, fill=tk.X)
        
        # Server status
        ttk.Label(info_frame, text=f"🌐 Server: localhost:{HTTP_PORT}", 
                 font=("Segoe UI", 8), foreground="#7d8da1").pack(side=tk.LEFT)
        
        # Signal target
        self.target_var = tk.StringVar(value="📡 Signal: None")
        ttk.Label(info_frame, textvariable=self.target_var, 
                 font=("Segoe UI", 8), foreground="#7d8da1").pack(side=tk.RIGHT)

    def start_server_thread(self):
        self.server_thread = threading.Thread(target=self.run_server, daemon=True)
        self.server_thread.start()

    def run_server(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        app = web.Application()
        app.router.add_post('/play', self.handle_play)
        app.router.add_post('/set_signal_target', self.handle_set_target)
        
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, '0.0.0.0', HTTP_PORT)
        loop.run_until_complete(site.start())
        print(f"✅ Server started on port {HTTP_PORT}")
        loop.run_forever()

    async def handle_play(self, request):
        try:
            reader = await request.multipart()
            field = await reader.next()
            
            if field.name == 'audio':
                total_bytes = 0
                while True:
                    chunk = await field.read_chunk(size=CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    self.audio_queue.put(chunk)
                
                print(f"✅ Received {total_bytes} bytes")
                return web.Response(text="Playback complete")
            
            return web.Response(status=400, text="No audio field found")
        except Exception as e:
            print(f"❌ Error in handle_play: {e}")
            return web.Response(status=500, text=str(e))

    async def handle_set_target(self, request):
        try:
            data = await request.json()
            self.signal_target_url = data.get('url')
            self.target_var.set(f"📡 Signal: {self.signal_target_url}")
            return web.Response(text=f"Target set to {self.signal_target_url}")
        except Exception as e:
            return web.Response(status=400, text=str(e))

    def start_audio_thread(self):
        threading.Thread(target=self.audio_processing_loop, daemon=True).start()

    def audio_processing_loop(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)
        print("🎵 Audio processing loop started")
        
        while True:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                self.is_playing = True
                
                # Play audio
                stream.write(chunk)
                
                # Calculate RMS with NaN protection
                try:
                    audio_data = np.frombuffer(chunk, dtype=np.int16)
                    if len(audio_data) > 0:
                        # Calculate RMS safely
                        squared = audio_data.astype(np.float64) ** 2
                        mean_squared = np.mean(squared)
                        
                        # Protect against NaN and inf
                        if np.isfinite(mean_squared) and mean_squared >= 0:
                            rms = np.sqrt(mean_squared)
                            
                            # Normalize with better scaling
                            # Typical speech RMS: 1000-15000
                            normalized_rms = min(max(rms / 12000.0, 0.0), 1.0)
                            
                            # Update with smoothing
                            self.current_signal = normalized_rms
                            self.current_rms = rms
                            self.signal_history.append(normalized_rms)
                        else:
                            # Fallback to zero if calculation fails
                            self.current_signal = 0.0
                            self.current_rms = 0.0
                            self.signal_history.append(0.0)
                    else:
                        self.current_signal = 0.0
                        self.current_rms = 0.0
                        self.signal_history.append(0.0)
                        
                except (ValueError, OverflowError) as e:
                    print(f"⚠️ Audio calculation error: {e}")
                    self.current_signal = 0.0
                    self.current_rms = 0.0
                    self.signal_history.append(0.0)
                
                # Send Signal (if target configured)
                if self.signal_target_url and np.isfinite(self.current_signal):
                    try:
                        threading.Thread(
                            target=requests.post, 
                            args=(self.signal_target_url,),
                            kwargs={'json': {'signal': float(self.current_signal)}, 'timeout': 1},
                            daemon=True
                        ).start()
                    except Exception:
                        pass
                        
            except queue.Empty:
                self.is_playing = False
                # Decay signal smoothly
                if self.current_signal > 0.01:
                    self.current_signal *= 0.9
                    self.signal_history.append(self.current_signal)
                else:
                    self.current_signal = 0.0
                    self.current_rms = 0.0
                    self.signal_history.append(0.0)
                    
            except Exception as e:
                print(f"❌ Audio Error: {e}")

    def update_ui(self):
        """Update visualization"""
        try:
            # Get signal with NaN protection
            signal = self.current_signal if np.isfinite(self.current_signal) else 0.0
            signal = max(0.0, min(1.0, signal))  # Clamp to [0, 1]
            
            # === Update Waveform Bars ===
            history_list = list(self.signal_history)
            
            for i, bar in enumerate(self.bars):
                # Map bar index to history (right to left, newest on right)
                history_idx = int((i / self.num_bars) * len(history_list))
                
                if history_idx < len(history_list):
                    bar_signal = history_list[history_idx]
                else:
                    bar_signal = 0.0
                
                # Protect against NaN
                if not np.isfinite(bar_signal):
                    bar_signal = 0.0
                
                # Calculate bar height (symmetric around center)
                bar_height = bar_signal * (self.wave_height / 2) * 0.8
                
                center = self.wave_height // 2
                y1 = center - bar_height
                y2 = center + bar_height
                
                # Get bar position
                coords = self.wave_canvas.coords(bar)
                x1, x2 = coords[0], coords[2]
                
                # Update bar
                self.wave_canvas.coords(bar, x1, y1, x2, y2)
                
                # Color gradient based on intensity
                if bar_signal > 0.7:
                    color = "#ff6b9d"  # Pink for loud
                elif bar_signal > 0.4:
                    color = "#feca57"  # Yellow for medium
                elif bar_signal > 0.1:
                    color = "#5dfdcb"  # Cyan for soft
                else:
                    color = "#1f4068"  # Dark for silence
                
                self.wave_canvas.itemconfig(bar, fill=color)
            
            # === Update Volume Meter ===
            meter_width = min(signal * 396, 396)
            self.meter_canvas.coords(self.volume_bar, 2, 2, meter_width + 2, 28)
            
            # Color based on volume
            if signal > 0.8:
                meter_color = "#ff6b9d"
            elif signal > 0.5:
                meter_color = "#feca57"
            else:
                meter_color = "#5dfdcb"
            
            self.meter_canvas.itemconfig(self.volume_bar, fill=meter_color)
            
            # Update percentage
            percentage = int(signal * 100)
            self.volume_var.set(f"{percentage}%")
            
            # === Update Status ===
            if self.is_playing:
                rms_val = self.current_rms if np.isfinite(self.current_rms) else 0.0
                self.status_var.set(f"🔊 Playing... | Volume: {percentage}% | RMS: {rms_val:.0f}")
            else:
                self.status_var.set("🎵 Ready - Waiting for audio...")
                
        except Exception as e:
            print(f"⚠️ UI update error: {e}")
        
        # Schedule next update
        self.root.after(30, self.update_ui)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    print("=" * 50)
    print("🎵 Fish TTS Audio Player")
    print("=" * 50)
    app = AudioPlayerApp()
    app.run()