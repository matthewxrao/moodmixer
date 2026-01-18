from pdb import run
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageOps
import cv2
import threading
import time
import gpiozero as gz
from matplotlib import text
import numpy as np

from picamera2 import Picamera2

import serial
import serial.tools.list_ports

ARDUINO_PORT = "/dev/ttyACM0"   # change if needed: /dev/ttyUSB0
ARDUINO_BAUD = 115200


MOOD_ADVICE = {
    "HAPPY":   '''You're riding a good wave. Share the energy—text someone you like and do one small thing you've been putting off.''',
    "SAD":     '''Go easy on yourself today. Drink some water, get a little sunlight if you can, and do one comfort task—music, shower, or a quick walk.''',
    "ANGRY":   '''Take 60 seconds to reset—slow breath in/out. Then channel it: move your body or write a quick "what I'm mad about" note.''',
    "FEAR":    '''You're in alert mode. Name 1 thing you can control right now, do it, then take a 2-minute grounding break (look around, feel your feet).''',
    "SURPRISE":'''Pause and re-check what happened. If it's good—enjoy it. If it's stressful—slow down and get one more piece of info before acting.''',
    "DISGUST": '''That reaction is real. Step away from the trigger and reset—fresh air, water, or switching tasks for a few minutes helps.''',
    "NEUTRAL": '''You're steady. Great time to do something productive—pick one simple task and knock it out clean.'''
}

class FaceScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Face Scanner")
        self.root.geometry("900x800")
        self.root.configure(bg="#0f0f12")  # dark modern background

        self.picam2 = None
        self.running = False
        self.face_detected = False
        self.detection_start_time = None
        self.photo_taken = False
        self.scan_progress = 0

        self.width = 640
        self.height = 380
        self.radius = 40  # how rounded the corners are

        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        self.serial = None
        self.connect_arduino()

        self.create_start_screen()

    # CONNECTING ARDUINO FOR INPUT
    def connect_arduino(self):
        # try to open serial port
        try:
            self.serial = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
            time.sleep(2)
            print(f"Connected to Arduino on {ARDUINO_PORT}")
        except serial.SerialException as e:
            print(f"Error connecting to Arduino: {(e)}")
            for p in serial.tools.list_ports.comports():
                print(f" - {p.device}: {p.description}")


    # SENDING MESSAGES TO ARDUINO
    def send_to_arduino(self, message):
        if not self.serial:
            raise RuntimeError("Arduino not connected")

        line = (message.strip() + "\n").encode('utf-8')
        self.serial.write(line)
        self.serial.flush()


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

        # Add exit button
        exit_btn = tk.Label(
            container,
            text="EXIT",
            font=("Helvetica", 12, "bold"),
            bg="#0f0f12",
            fg="#ff4444",
            cursor="hand2",
            padx=30,
            pady=10
        )
        exit_btn.pack(pady=(30, 0))
        exit_btn.bind("<Button-1>", lambda e: self.on_closing())
        exit_btn.bind("<Enter>", lambda e: exit_btn.configure(fg="#ff6666"))
        exit_btn.bind("<Leave>", lambda e: exit_btn.configure(fg="#ff4444"))

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

        # Create text on canvas instead of using Label
        self.status_text_id = self.canvas.create_text(
            (self.width + 20) // 2,
            self.height + 60,
            text="Look at the camera",
            font=("Helvetica", 18),
            fill="#666677"
        )

        cancel_lbl = tk.Label(
            self.scanner_container,
            text="CANCEL",
            font=("Helvetica", 12, "bold"),
            bg="#0f0f12",
            fg="#ff4444",
            cursor="hand2"
        )
        cancel_lbl.pack(pady=30)
        cancel_lbl.bind("<Button-1>", lambda e: self.cancel_scan())


    def show_report_and_user_selection_screen(self, dominant, emotions):
        # check getting the emotions
        self._clear_window()

        container = tk.Frame(self.root, bg="#0f0f12")
        container.place(relx=0.5, rely=0.5, anchor="center")

        # show all the emotions and confidence levels
        tk.Label(
            container,
            text="MOOD DETECTED",
            font=("Helvetica", 14),
            bg="#0f0f12",
            fg="#666677",
        ).pack(pady=10)

        tk.Label(
            container,
            text=dominant.upper(),
            font=("Helvetica", 48, "bold"),
            bg="#0f0f12",
            fg="#ffffff",
        ).pack(pady=20)

        # button to make drink

        advice = MOOD_ADVICE.get(dominant.upper(), MOOD_ADVICE["NEUTRAL"])

        tk.Label(
            container,
            text=advice,
            font=("Helvetica", 14),
            bg="#0f0f12",
            fg="#aaaaaa",
            wraplength=650,
            justify="center"
        ).pack(pady=(0, 20))

        top = sorted(emotions.items(), key=lambda x: x[1], reverse=True)[:5]

        perc_frame = tk.Frame(container, bg="#0f0f12")
        perc_frame.pack(pady=(0,25))

        tk.Label(
            perc_frame,
            text="Emotion Confidence Levels:",
            font=("Helvetica", 12, "bold"),
            bg="#0f0f12",
            fg="#666677"
        ).pack(pady=(0,10))

        for emotion, val in top:
            tk.Label(
                perc_frame,
                text=f"{emotion.upper():<10}: {val:.1f}%",
                font=("Helvetica", 12),
                bg="#0f0f12",
                fg="#aaaaaa"
            ).pack()

        btn_row = tk.Frame(container, bg="#0f0f12")
        btn_row.pack(pady=(10, 0))

        make_drink_btn = tk.Label(
            btn_row,
            text="MAKE DRINK",
            font=("Helvetica", 16, "bold"),
            bg="#00ff88",
            fg="#0f0f12",
            padx=40,
            pady=15,
            cursor="hand2",
        )

        make_drink_btn.pack(side="left", padx=10)
        make_drink_btn.bind("<Button-1>", lambda e: self.start_drink_flow(dominant))

        again_btn = tk.Label(
            btn_row,
            text="SCAN AGAIN",
            font=("Helvetica", 16, "bold"),
            bg="#ffffff",
            fg="#0f0f12",
            padx=40,
            pady=15,
            cursor="hand2",
        )

        again_btn.pack(side="left", padx=10)
        again_btn.bind("<Button-1>", lambda e: self.create_start_screen())


    def show_making_screen(self, emotion, drink_name):
        self._clear_window()

        container = tk.Frame(self.root, bg="#0f0f12")
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            container,
            text="DISPENSING",
            font=("Helvetica", 14),
            bg="#0f0f12",
            fg="#666677",
        ).pack(pady=10)

        tk.Label(
            container,
            text=f"Mood: {emotion.upper()}",
            font=("Helvetica", 44, "bold"),
            bg="#0f0f12",
            fg="#00ff88",
        ).pack(pady=(5, 10))

        tk.Label(
            container,
            text=f"Making: {drink_name}",
            font=("Helvetica", 18, "bold"),
            bg="#0f0f12",
            fg="#ffffff",
        ).pack(pady=(0, 20))

        self.status_label = tk.Label(
            container,
            text="Starting...",
            font=("Helvetica", 14),
            bg="#0f0f12",
            fg="#aaaaaa",
        )
        self.status_label.pack(pady=10)

        cancel_lbl = tk.Label(
            container,
            text="CANCEL",
            font=("Helvetica", 12, "bold"),
            bg="#0f0f12",
            fg="#ff4444",
            cursor="hand2",
        )

        cancel_lbl.pack(pady=20)
        cancel_lbl.bind("<Button-1>", lambda e: self.cancel_scan())

    def show_done_screen(self, emotion: str, drink_name: str):
        self._clear_window()

        container = tk.Frame(self.root, bg="#0f0f12")
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            container,
            text="DONE",
            font=("Helvetica", 14),
            bg="#0f0f12",
            fg="#666677",
        ).pack(pady=10)

        tk.Label(
            container,
            text=drink_name,
            font=("Helvetica", 34, "bold"),
            bg="#0f0f12",
            fg="#00ff88",
        ).pack(pady=10)

        tk.Label(
            container,
            text=f"Mood: {emotion}",
            font=("Helvetica", 16),
            bg="#0f0f12",
            fg="#ffffff",
        ).pack(pady=10)

        reset_btn = tk.Label(
            container,
            text="SCAN AGAIN",
            font=("Helvetica", 14, "bold"),
            bg="#ffffff",
            fg="#0f0f12",
            padx=40,
            pady=15,
            cursor="hand2",
        )
        reset_btn.pack(pady=30)
        reset_btn.bind("<Button-1>", lambda e: self.create_start_screen())



    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def start_scanning(self):
        self.create_scanner_screen()

        self.picam2 = Picamera2()

        config = self.picam2.create_preview_configuration(
            main={"size": (self.width, self.height), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()

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
            frame = self.picam2.capture_array()

            frame_bgr = frame

            frame_bgr = cv2.flip(frame_bgr, 1)

            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.2, 5)

            if len(faces) > 0:
                if not self.face_detected:
                    self.face_detected = True
                    self.detection_start_time = time.time()

                elapsed = time.time() - self.detection_start_time
                progress = min(elapsed / 2.0, 1.0)

                if progress >= 0.25:
                    self.photo_taken = True
                    self.picam2.stop()
                    self.picam2.close()
                    self.picam2 = None
                    self.root.after(0, lambda: self.capture_and_analyze(frame_bgr))
                    break

                ring_color = (0, 255, 136)
                status_text = "Hold still..."
            else:
                self.face_detected = False
                self.detection_start_time = None
                progress = 0
                ring_color = (255, 68, 68)
                status_text = "Searching for face..."

            self.root.after(0, lambda text=status_text: self.update_status(text))

            img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)

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

            time.sleep(0.05)

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
        # Update canvas text instead of label
        if hasattr(self, 'status_text_id'):
            self.canvas.itemconfig(self.status_text_id, text=text)
        elif hasattr(self, 'status_label'):
            self.status_label.config(text=text)

    def capture_and_analyze(self, frame):
        self.update_status("Analyzing...")

        cv2.imwrite("captured_face.jpg", frame)

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
                dominant = sorted_emotions[0][0].upper()
                self.root.after(0, lambda d=dominant, emo=emotions: self.show_report_and_user_selection_screen(d, emo))


            except ImportError:
                print("\nERROR: DeepFace not installed! Run `pip install deepface`\n")
            except Exception as e:
                print(f"\nERROR: {str(e)}\n")
                self.root.after(0, self.cancel_scan)

        threading.Thread(target=analyze, daemon=True).start()

    def start_drink_flow(self, dominant: str):

        if not self.serial:
            self.update_status("Arduino not connected")
            return

        # choose drink

        dominant = dominant.upper()
        drink_name = f"{dominant.title()} Mix"
        self.last_drink_name = drink_name

        self.show_making_screen(dominant, drink_name)

        def status(msg):
            self.root.after(0, lambda: self.update_status(msg))

        def do_serial():
            try:
                status("sending command to Arduino")
                self.send_to_arduino(f"DISPENSE {dominant}")

                status("dispensing...")
                time.sleep(2)


                status("Drink ready")
                self.root.after(800, lambda: self.show_done_screen(dominant, drink_name))

            except Exception as e:
                print(f"Serial error: {e}")
                self.root.after(0, self.cancel_scan)

        threading.Thread(target=do_serial, daemon=True).start()

    def cancel_scan(self):
        self.running = False

        if self.picam2:
            self.picam2.stop()
            self.picam2 = None
        self.create_start_screen()

    def on_closing(self):
        self.running = False
        if self.picam2:
            self.picam2.stop()
        try:
            if self.serial:
                self.serial.close()
        except Exception:
            pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    # root.overridedirect(True)
    app = FaceScannerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
