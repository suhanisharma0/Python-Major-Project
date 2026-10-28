#!/usr/bin/env python3
"""Screen recorder with a Start/Stop window (tkinter + mss + OpenCV).

Run:  py -3.11 recorder_gui.py
"""
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

import cv2
import mss
import numpy as np

# mss.MSS is the new name; fall back for older versions
MSS = getattr(mss, "MSS", None) or mss.mss


class RecorderApp:
    def __init__(self, root):
        self.root = root
        root.title("Screen Recorder")
        root.geometry("340x260")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        self.recording = False
        self.thread = None
        self.stop_event = threading.Event()
        self.start_time = 0.0
        self.error = None

        self.folder = tk.StringVar(value=".")
        self.fps = tk.IntVar(value=20)
        self.scale = tk.DoubleVar(value=1.0)
        self.status = tk.StringVar(value="Ready")
        self.timer = tk.StringVar(value="00:00")

        pad = {"padx": 10, "pady": 4}

        row = tk.Frame(root)
        row.pack(fill="x", **pad)
        tk.Label(row, text="Save to:").pack(side="left")
        tk.Entry(row, textvariable=self.folder, width=22).pack(side="left", padx=4)
        tk.Button(row, text="...", width=3, command=self.pick_folder).pack(side="left")

        row = tk.Frame(root)
        row.pack(fill="x", **pad)
        tk.Label(row, text="FPS:").pack(side="left")
        tk.Spinbox(row, from_=5, to=60, textvariable=self.fps, width=5).pack(side="left", padx=4)
        tk.Label(row, text="Scale:").pack(side="left", padx=(12, 0))
        tk.Spinbox(row, from_=0.25, to=1.0, increment=0.25, textvariable=self.scale,
                   width=5).pack(side="left", padx=4)

        tk.Label(root, textvariable=self.timer, font=("Segoe UI", 28, "bold")).pack(pady=6)

        self.btn = tk.Button(root, text="● Start Recording", font=("Segoe UI", 12),
                             bg="#2e7d32", fg="white", height=2, command=self.toggle)
        self.btn.pack(fill="x", padx=20)

        tk.Label(root, textvariable=self.status, fg="gray").pack(pady=6)

        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def pick_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.folder.set(d)

    def toggle(self):
        if self.recording:
            self.stop()
        else:
            self.start()

    def start(self):
        try:
            fps = int(self.fps.get())
            scale = float(self.scale.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "FPS and Scale must be numbers.")
            return
        name = f"recording_{datetime.now():%Y%m%d_%H%M%S}.mp4"
        out = os.path.join(self.folder.get(), name)

        self.error = None
        self.stop_event.clear()
        self.recording = True
        self.start_time = time.perf_counter()
        self.btn.config(text="■ Stop Recording", bg="#c62828")
        self.status.set("Recording...")
        self.out_path = out

        self.thread = threading.Thread(target=self.record, args=(out, fps, scale), daemon=True)
        self.thread.start()
        self.tick()

    def stop(self):
        self.stop_event.set()
        self.recording = False
        self.btn.config(state="disabled", text="Saving...")
        self.root.after(100, self.wait_finish)

    def wait_finish(self):
        if self.thread and self.thread.is_alive():
            self.root.after(100, self.wait_finish)
            return
        self.btn.config(state="normal", text="● Start Recording", bg="#2e7d32")
        if self.error:
            self.status.set("Error")
            messagebox.showerror("Recording failed", self.error)
        else:
            self.status.set(f"Saved: {self.out_path}")

    def tick(self):
        if self.recording:
            s = int(time.perf_counter() - self.start_time)
            self.timer.set(f"{s // 60:02d}:{s % 60:02d}")
            self.root.after(500, self.tick)

    def record(self, out, fps, scale):
        try:
            with MSS() as sct:
                area = sct.monitors[1]
                w = int(area["width"] * scale)
                h = int(area["height"] * scale)
                w -= w % 2
                h -= h % 2
                writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                if not writer.isOpened():
                    raise RuntimeError("Could not open video writer.")
                frame_time = 1.0 / fps
                next_t = time.perf_counter()
                while not self.stop_event.is_set():
                    img = np.array(sct.grab(area))
                    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    if frame.shape[1] != w or frame.shape[0] != h:
                        frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
                    writer.write(frame)
                    next_t += frame_time
                    delay = next_t - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
                    else:
                        next_t = time.perf_counter()
                writer.release()
        except Exception as e:  # shown to the user in wait_finish
            self.error = str(e)

    def on_close(self):
        if self.recording:
            self.stop_event.set()
            if self.thread:
                self.thread.join(timeout=3)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    RecorderApp(root)
    root.mainloop()
