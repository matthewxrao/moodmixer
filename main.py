import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageOps
import cv2
import threading
import time
import math

class FaceScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Face Scanner")
        self.root.geometry("900x800")
        self.root.configure(bg="#0f0f12")  # dark modern background
        
        self.cap = None
        self.running = False
        self.face_detected = False
        self.detection_start_time = None
        self.photo_taken = False
        self.scan_progress = 0
        
        self.width = 640
        self.height = 480
        self.radius = 40  # how rounded the corners are
        
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        self.create_start_screen()
        
    def create_start_screen(self):
        self._clear_window()
        
        # main container to hold everything
        container = tk.Frame(self.root, bg="#0f0f12")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(
            container,
            text="MOODMIXER",
            font=("Helvetica", 48, "bold"),
            bg="#0f0f12",
            fg="#ffffff"
        ).pack(pady=(0, 10))
        
        tk.Label(
            container,
            text="EMOTION ANALYSIS",
            font=("Helvetica", 14, "bold"),
            bg="#0f0f12",
            fg="#4a4a5e",
        ).pack(pady=(0, 60))
        
        self.start_btn = tk.Label(
            container,
            text="BEGIN SCAN",
            font=("Helvetica", 16, "bold"),
            bg="#ffffff",
            fg="#0f0f12",
            padx=50,
            pady=20,
            cursor="hand2"
        )
        self.start_btn.pack()
        self.start_btn.bind("<Button-1>", lambda e: self.start_scanning())
        self.start_btn.bind("<Enter>", lambda e: self.start_btn.configure(bg="#e0e0e0"))
        self.start_btn.bind("<Leave>", lambda e: self.start_btn.configure(bg="#ffffff"))
        
    def create_scanner_screen(self):
        self._clear_window()
        
        self.scanner_container = tk.Frame(self.root, bg="#0f0f12")
        self.scanner_container.pack(expand=True, fill="both", padx=50, pady=50)
        
        self.canvas = tk.Canvas(
            self.scanner_container,
            width=self.width + 20, # extra space for glowing ring
            height=self.height + 20,
            bg="#0f0f12",
            highlightthickness=0
        )
        self.canvas.pack(pady=20)
        
        self.status_label = tk.Label(
            self.scanner_container,
            text="Look at the camera",
            font=("Helvetica", 18),
            bg="#0f0f12",
            fg="#666677"
        )
        self.status_label.pack(pady=30)
        
        cancel_lbl = tk.Label(
            self.scanner_container,
            text="CANCEL",
            font=("Helvetica", 12, "bold"),
            bg="#0f0f12",
            fg="#ff4444",
            cursor="hand2"
        )
        cancel_lbl.pack()
        cancel_lbl.bind("<Button-1>", lambda e: self.cancel_scan())
        
    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def start_scanning(self):
        self.create_scanner_screen()
        self.cap = cv2.VideoCapture(0)
        self.running = True
        self.photo_taken = False
        self.face_detected = False
        self.detection_start_time = None
        
        threading.Thread(target=self.update_frame, daemon=True).start()
        
    def round_rectangle(self, size, radius, fill):
        width, height = size
        circle = Image.new('L', (radius * 2, radius * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
        
        alpha = Image.new('L', size, 255)
        w, h = size
        
        alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
        alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, h - radius))
        alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius, 0))
        alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (w - radius, h - radius))
        
        draw = ImageDraw.Draw(alpha)
        draw.rectangle((radius, 0, w - radius, h), fill=255)
        draw.rectangle((0, radius, w, h - radius), fill=255)
        
        return alpha

    def add_corners(self, im, rad):
        circle = Image.new('L', (rad * 2, rad * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
        
        alpha = Image.new('L', im.size, 255)
        w, h = im.size
        
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        
        im.putalpha(alpha)
        return im

    def update_frame(self):
        while self.running and not self.photo_taken:
            ret, frame = self.cap.read()
            if not ret:
                break
                
            frame = cv2.flip(frame, 1)
            frame_resized = cv2.resize(frame, (self.width, self.height))
            
            # try to find a face
            gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.2, 5)
            
            # logic for handling detection state
            if len(faces) > 0:
                if not self.face_detected:
                    self.face_detected = True
                    self.detection_start_time = time.time()
                
                elapsed = time.time() - self.detection_start_time
                progress = min(elapsed / 2.0, 1.0)
                
                if progress >= 1.0:
                    self.photo_taken = True
                    self.root.after(0, lambda: self.capture_and_analyze(frame))
                    break
                    
                ring_color = (0, 255, 136) # green implies good
                status_text = "Hold still..."
            else:
                self.face_detected = False
                self.detection_start_time = None
                progress = 0
                ring_color = (255, 68, 68) # red implies waiting
                status_text = "Searching for face..."
            
            # update ui on main thread so it doesn't crash
            self.root.after(0, lambda: self.update_status(status_text))
            
            # prep image for display
            img_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            # round those corners
            pil_img = self.add_corners(pil_img, self.radius)
            
            # draw the ring/border
            # make a transparent layer just for this
            output_img = Image.new('RGBA', (self.width + 20, self.height + 20), (0, 0, 0, 0))
            output_img.paste(pil_img, (10, 10), pil_img)
            
            draw = ImageDraw.Draw(output_img)
            
            x0, y0 = 10, 10
            x1, y1 = self.width + 10, self.height + 10
            r = self.radius
            
            # set the color
            color = ring_color
            
            # make it thick enough to see
            stroke = 6
            # corners
            draw.arc((x0, y0, x0 + r*2, y0 + r*2), 180, 270, fill=color, width=stroke)
            draw.arc((x1 - r*2, y0, x1, y0 + r*2), 270, 0, fill=color, width=stroke)
            draw.arc((x0, y1 - r*2, x0 + r*2, y1), 90, 180, fill=color, width=stroke)
            draw.arc((x1 - r*2, y1 - r*2, x1, y1), 0, 90, fill=color, width=stroke)
            
            # lines connecting corners
            draw.line((x0 + r, y0, x1 - r, y0), fill=color, width=stroke)
            draw.line((x0 + r, y1, x1 - r, y1), fill=color, width=stroke)
            draw.line((x0, y0 + r, x0, y1 - r), fill=color, width=stroke)
            draw.line((x1, y0 + r, x1, y1 - r), fill=color, width=stroke)
            
            imgtk = ImageTk.PhotoImage(image=output_img)
            self.root.after(0, lambda i=imgtk: self.update_canvas(i))
            
            time.sleep(0.01)

    def update_canvas(self, imgtk):
        if not self.running: return
        self.canvas.create_image(
            self.width//2 + 10, 
            self.height//2 + 10, 
            anchor=tk.CENTER, 
            image=imgtk
        )
        self.canvas.imgtk = imgtk

    def update_status(self, text):
        if hasattr(self, 'status_label'):
            self.status_label.config(text=text)

    def capture_and_analyze(self, frame):
        cv2.imwrite("captured_face.jpg", frame)
        self.update_status("Analyzing...")
        
        # freeze the video
        
        def analyze():            
            print("\n" + "="*60)
            print("  MOODMIXER ANALYSIS RESULT")
            print("="*60)
            
            try:
                from deepface import DeepFace
                
                result = DeepFace.analyze(
                    "captured_face.jpg",
                    actions=['emotion'],
                    enforce_detection=False,
                    silent=True
                )
                
                if isinstance(result, list):
                    emotions = result[0]['emotion']
                else:
                    emotions = result['emotion']
                
                sorted_emotions = sorted(emotions.items(), key=lambda x: x[1], reverse=True)
                
                print("\n  DETECTED EMOTIONS:")
                print("  " + "-" * 56)
                for emotion, confidence in sorted_emotions:
                    bar_len = int(confidence / 2.5)
                    bar = "█" * bar_len
                    print(f"  {emotion.upper():<12} | {bar:<40} {confidence:.1f}%")
                
                print("\n  " + "-" * 56)
                print(f"  DOMINANT: {sorted_emotions[0][0].upper()}")
                print("="*60 + "\n")
                
                # update ui to show we're done
                self.root.after(0, lambda: self.show_result(sorted_emotions[0][0].upper()))
                
            except ImportError:
                print("\nERROR: DeepFace not installed! Run `pip install deepface`\n")
            except Exception as e:
                print(f"\nERROR: {str(e)}\n")
                self.root.after(0, self.cancel_scan)

        threading.Thread(target=analyze, daemon=True).start()

    def show_result(self, emotion):
        self._clear_window()
        
        container = tk.Frame(self.root, bg="#0f0f12")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(
            container,
            text="MOOD DETECTED",
            font=("Helvetica", 14),
            bg="#0f0f12",
            fg="#666677"
        ).pack(pady=10)
        
        tk.Label(
            container,
            text=emotion,
            font=("Helvetica", 48, "bold"),
            bg="#0f0f12",
            fg="#00ff88"
        ).pack(pady=20)
        
        tk.Label(
            container,
            text="Check terminal for full report",
            font=("Helvetica", 12),
            bg="#0f0f12",
            fg="#444455"
        ).pack(pady=30)
        
        # reset button
        reset_btn = tk.Label(
            container,
            text="SCAN AGAIN",
            font=("Helvetica", 14, "bold"),
            bg="#ffffff",
            fg="#0f0f12",
            padx=40,
            pady=15,
            cursor="hand2"
        )
        reset_btn.pack(pady=20)
        reset_btn.bind("<Button-1>", lambda e: self.create_start_screen())

    def cancel_scan(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.create_start_screen()
        
    def on_closing(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FaceScannerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()