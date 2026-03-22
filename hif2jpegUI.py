import os
import glob
import queue
import logging
import threading
import platform
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ExifTags

# Safeguard for external dependencies
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    messagebox.showerror("Dependency Error", "Please install pillow-heif: pip install pillow-heif")

try:
    import sv_ttk
    HAS_THEME = True
except ImportError:
    HAS_THEME = False

# ... [Keep your COLOR_SCHEME and logging setup here] ...

class HEIFtoJPEGConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HEIF to JPEG Converter v1.1.0")
        
        # UI Variables
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.quality = tk.IntVar(value=90)
        self.status_var = tk.StringVar(value="Ready")
        self.dark_mode = tk.BooleanVar(value=False)
        self.include_subdirs = tk.BooleanVar(value=False)
        self.preserve_exif = tk.BooleanVar(value=True)
        self.preserve_structure = tk.BooleanVar(value=True)
        self.rename_pattern = tk.StringVar(value="{name}")
        self.max_workers = tk.IntVar(value=min(4, os.cpu_count() or 2))
        
        self.file_list = []
        self.conversion_running = False
        self.converter = ImageConverter()

        if HAS_THEME:
            sv_ttk.set_theme("light")
        
        self.setup_styles()
        self.create_widgets()
        self.create_menu()
        
        # Trace for theme toggle
        self.dark_mode.trace_add("write", self.toggle_theme)

    def toggle_theme(self, *args):
        if HAS_THEME:
            theme = "dark" if self.dark_mode.get() else "light"
            sv_ttk.set_theme(theme)

    def start_conversion(self):
        """Thread-safe start mechanism"""
        if self.conversion_running:
            return
        if not self.file_list:
            messagebox.showwarning("Empty List", "No files selected for conversion.")
            return
            
        target_out = self.output_dir.get() or self.input_dir.get()
        if not os.path.exists(target_out):
            os.makedirs(target_out, exist_ok=True)

        self.conversion_running = True
        self.convert_btn.config(state="disabled")
        
        # Start background thread
        threading.Thread(target=self.conversion_logic, args=(target_out,), daemon=True).start()

    def conversion_logic(self, output_path):
        """Background process that communicates safely with the UI thread"""
        success_count = 0
        error_count = 0
        total = len(self.file_list)
        
        with ThreadPoolExecutor(max_workers=self.max_workers.get()) as executor:
            tasks = {
                executor.submit(
                    self.converter.convert_image,
                    f, output_path, self.quality.get(),
                    self.preserve_structure.get(), self.preserve_exif.get(),
                    self.rename_pattern.get() if self.rename_pattern.get() != "{name}" else None
                ): f for f in self.file_list
            }
            
            for i, future in enumerate(tasks):
                if self.converter.stop_requested: break
                try:
                    success, _ = future.result()
                    if success: success_count += 1
                    else: error_count += 1
                except Exception:
                    error_count += 1
                
                # Signal UI thread to update
                self.root.after(0, self.update_ui_progress, i + 1, total)

        self.root.after(0, self.finalize_conversion, success_count, error_count)

    def update_ui_progress(self, current, total):
        self.progress["value"] = current
        self.status_var.set(f"Processing: {current}/{total}")

    def finalize_conversion(self, s, e):
        self.conversion_running = False
        self.convert_btn.config(state="normal")
        self.status_var.set(f"Complete: {s} successful, {e} failed.")
        messagebox.showinfo("Conversion Finished", f"Processed {s+e} files total.")

# ... [Keep your widget creation and logic methods below] ...
