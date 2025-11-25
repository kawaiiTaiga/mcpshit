import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os
from config_manager import ConfigManager
from wakeword_client import WakeWordClient, STATUS_IDLE, STATUS_LISTENING, STATUS_WAKED, STATUS_RECORDING, STATUS_PROCESSING, STATUS_TYPED

class STTStatusBar:
    def __init__(self, root):
        self.root = root
        self.root.title("STT Bar")
        self.root.geometry("300x40")
        self.root.overrideredirect(True) # Remove window decorations
        self.root.attributes('-topmost', True) # Always on top
        self.root.configure(bg='#2b2b2b')

        # Center the window horizontally at the top
        screen_width = self.root.winfo_screenwidth()
        x_pos = (screen_width - 300) // 2
        self.root.geometry(f"+{x_pos}+10")

        self.config_manager = ConfigManager()
        self.client_thread = None
        self.is_running = False
        self.client = None
        self.settings_window = None
        
        # Dragging functionality
        self.root.bind('<Button-1>', self.start_move)
        self.root.bind('<B1-Motion>', self.do_move)

        self.create_widgets()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def create_widgets(self):
        # Main Frame
        main_frame = tk.Frame(self.root, bg='#2b2b2b')
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Status Canvas (Custom Visual)
        self.status_canvas = tk.Canvas(main_frame, width=150, height=30, bg='#2b2b2b', highlightthickness=0)
        self.status_canvas.pack(side='left', padx=5)
        self.draw_status("Sleeping", "#555555", 0.0)

        # Start/Stop Button
        self.toggle_btn = tk.Button(main_frame, text="▶", command=self.toggle_listening, 
                                    bg='#4CAF50', fg='white', relief='flat', width=3)
        self.toggle_btn.pack(side='left', padx=5)

        # Settings Button
        self.settings_btn = tk.Button(main_frame, text="⚙", command=self.open_settings, 
                                      bg='#555', fg='white', relief='flat', width=3)
        self.settings_btn.pack(side='left', padx=5)
        
        # Exit Button
        self.exit_btn = tk.Button(main_frame, text="X", command=self.exit_app, 
                                  bg='#d32f2f', fg='white', relief='flat', width=3)
        self.exit_btn.pack(side='right', padx=5)

    def draw_status(self, text, color, progress=1.0):
        self.status_canvas.delete("all")
        width = 150
        height = 30
        
        # Background Pill
        self.round_rectangle(0, 0, width, height, radius=15, fill="#333333", outline="")
        
        # Progress Fill
        fill_width = width * progress
        if fill_width > 0:
            self.round_rectangle(0, 0, fill_width, height, radius=15, fill=color, outline="")
            
        # Text
        self.status_canvas.create_text(width/2, height/2, text=text, fill="white", font=("Arial", 10, "bold"))

    def round_rectangle(self, x1, y1, x2, y2, radius=25, **kwargs):
        points = [x1+radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1]
        return self.status_canvas.create_polygon(points, **kwargs, smooth=True)

    def toggle_listening(self):
        if self.is_running:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):
        if self.is_running:
            return

        self.is_running = True
        self.toggle_btn.config(text="■", bg='#d32f2f')
        self.draw_status("Listening...", "#4CAF50", 0.2) # Initial state
        
        config = self.config_manager.config
        
        try:
            self.client = WakeWordClient(
                wakeword_models=config.get("wakeword_models", []),
                whisper_server_url=config.get("whisper_server_url"),
                wakeword_threshold=config.get("wakeword_threshold"),
                overlay_image_path=config.get("overlay_image_path"),
                overlay_sound_file=config.get("overlay_sound_file"),
                log_callback=self.log_callback,
                on_wakeword=self.on_wakeword_detected,
                status_callback=self.update_status_ui
            )
            
            self.client_thread = threading.Thread(target=self.run_client, daemon=True)
            self.client_thread.start()
            
        except Exception as e:
            print(f"Error initializing client: {e}")
            self.stop_listening()

    def run_client(self):
        try:
            self.client.run()
        except Exception as e:
            print(f"Client error: {e}")
            self.root.after(0, self.stop_listening)

    def stop_listening(self):
        self.is_running = False
        if self.client:
            self.client.stop()
        
        self.toggle_btn.config(text="▶", bg='#4CAF50')
        self.draw_status("Sleeping", "#555555", 0.0)

    def log_callback(self, message):
        # We rely on status_callback for UI updates now, but keep this for debug or fallback
        pass

    def update_status_ui(self, status):
        # Map status to (Text, Color, Progress)
        status_map = {
            STATUS_IDLE: ("Sleeping", "#555555", 0.0),
            STATUS_LISTENING: ("Listening...", "#4CAF50", 0.2), # Greenish
            STATUS_WAKED: ("Waked!", "#FFC107", 0.4),       # Amber
            STATUS_RECORDING: ("Recording...", "#FF5722", 0.6), # Orange
            STATUS_PROCESSING: ("Processing...", "#2196F3", 0.8), # Blue
            STATUS_TYPED: ("Typed!", "#9C27B0", 1.0)        # Purple
        }
        
        if status in status_map:
            text, color, progress = status_map[status]
            self.root.after(0, lambda: self.draw_status(text, color, progress))

    def on_wakeword_detected(self):
        # Schedule overlay on main thread
        self.root.after(0, self.show_overlay)

    def show_overlay(self):
        config = self.config_manager.config
        image_path = config.get("overlay_image_path")
        duration = config.get("overlay_duration_ms", 1500)

        if not image_path or not os.path.exists(image_path):
            return

        try:
            overlay = tk.Toplevel(self.root)
            overlay.title("WakeWord Overlay")
            
            screen_width = overlay.winfo_screenwidth()
            screen_height = overlay.winfo_screenheight()
            
            overlay.overrideredirect(True)
            overlay.geometry(f"{screen_width}x{screen_height}+0+0")
            overlay.attributes('-alpha', 1.0)
            overlay.attributes('-topmost', True)
            overlay.config(bg='black')
            
            pil_image = Image.open(image_path)
            tk_image = ImageTk.PhotoImage(pil_image)
            
            label = tk.Label(overlay, image=tk_image, bg='black')
            label.image = tk_image # Keep reference
            label.pack(expand=True)
            
            overlay.after(duration, overlay.destroy)
            
        except Exception as e:
            print(f"Overlay error: {e}")

    def open_settings(self):
        if self.settings_window and self.settings_window.window.winfo_exists():
            self.settings_window.window.lift()
            return
            
        self.settings_window = SettingsWindow(self.root, self.config_manager)

    def exit_app(self):
        self.stop_listening()
        self.root.destroy()


class SettingsWindow:
    def __init__(self, parent, config_manager):
        self.window = tk.Toplevel(parent)
        self.window.title("Settings")
        self.window.geometry("500x600")
        self.config_manager = config_manager
        
        self.create_widgets()
        self.load_settings()

    def create_widgets(self):
        frame = ttk.Frame(self.window, padding="10")
        frame.pack(fill='both', expand=True)

        # Whisper Server URL
        ttk.Label(frame, text="Whisper Server URL:").pack(anchor='w', pady=(0, 5))
        self.whisper_url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.whisper_url_var).pack(fill='x', pady=(0, 10))

        # Wakeword Models
        ttk.Label(frame, text="Wakeword Models (ONNX):").pack(anchor='w', pady=(0, 5))
        self.models_listbox = tk.Listbox(frame, height=5)
        self.models_listbox.pack(fill='x', pady=(0, 5))
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(btn_frame, text="Add Model", command=self.add_model).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Remove Selected", command=self.remove_model).pack(side='left')

        # Thresholds with Value Label
        ttk.Label(frame, text="Wakeword Threshold:").pack(anchor='w', pady=(0, 5))
        
        threshold_frame = ttk.Frame(frame)
        threshold_frame.pack(fill='x', pady=(0, 10))
        
        self.threshold_var = tk.DoubleVar()
        self.threshold_scale = ttk.Scale(threshold_frame, from_=0.0, to=1.0, variable=self.threshold_var, orient='horizontal', command=self.update_threshold_label)
        self.threshold_scale.pack(side='left', fill='x', expand=True)
        
        self.threshold_label = ttk.Label(threshold_frame, text="0.50", width=5)
        self.threshold_label.pack(side='right', padx=(5, 0))

        # Overlay Image
        ttk.Label(frame, text="Overlay Image Path:").pack(anchor='w', pady=(0, 5))
        img_frame = ttk.Frame(frame)
        img_frame.pack(fill='x', pady=(0, 10))
        self.overlay_img_var = tk.StringVar()
        ttk.Entry(img_frame, textvariable=self.overlay_img_var).pack(side='left', fill='x', expand=True)
        ttk.Button(img_frame, text="Browse", command=self.browse_image).pack(side='right', padx=(5, 0))

        # Sound File
        ttk.Label(frame, text="Sound File Path:").pack(anchor='w', pady=(0, 5))
        snd_frame = ttk.Frame(frame)
        snd_frame.pack(fill='x', pady=(0, 10))
        self.sound_file_var = tk.StringVar()
        ttk.Entry(snd_frame, textvariable=self.sound_file_var).pack(side='left', fill='x', expand=True)
        ttk.Button(snd_frame, text="Browse", command=self.browse_sound).pack(side='right', padx=(5, 0))

        # Save Button
        ttk.Button(frame, text="Save Settings", command=self.save_settings).pack(pady=20)

    def update_threshold_label(self, value):
        self.threshold_label.config(text=f"{float(value):.2f}")

    def load_settings(self):
        config = self.config_manager.config
        self.whisper_url_var.set(config.get("whisper_server_url", ""))
        
        threshold = config.get("wakeword_threshold", 0.5)
        self.threshold_var.set(threshold)
        self.update_threshold_label(threshold)
        
        self.overlay_img_var.set(config.get("overlay_image_path", ""))
        self.sound_file_var.set(config.get("overlay_sound_file", ""))
        
        self.models_listbox.delete(0, 'end')
        for model in config.get("wakeword_models", []):
            self.models_listbox.insert('end', model)

    def save_settings(self):
        models = list(self.models_listbox.get(0, 'end'))
        
        self.config_manager.set("whisper_server_url", self.whisper_url_var.get())
        self.config_manager.set("wakeword_models", models)
        self.config_manager.set("wakeword_threshold", self.threshold_var.get())
        self.config_manager.set("overlay_image_path", self.overlay_img_var.get())
        self.config_manager.set("overlay_sound_file", self.sound_file_var.get())
        
        self.config_manager.save_config()
        messagebox.showinfo("Success", "Settings saved!")
        self.window.destroy()

    def add_model(self):
        filename = filedialog.askopenfilename(filetypes=[("ONNX files", "*.onnx")])
        if filename:
            try:
                rel_path = os.path.relpath(filename)
                self.models_listbox.insert('end', rel_path)
            except ValueError:
                self.models_listbox.insert('end', filename)

    def remove_model(self):
        selection = self.models_listbox.curselection()
        if selection:
            self.models_listbox.delete(selection[0])

    def browse_image(self):
        filename = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.png *.jpeg")])
        if filename:
            self.overlay_img_var.set(filename)

    def browse_sound(self):
        filename = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if filename:
            self.sound_file_var.set(filename)

if __name__ == "__main__":
    root = tk.Tk()
    app = STTStatusBar(root)
    root.mainloop()
