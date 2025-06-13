#Checkout my other projects! https://github.com/Justagwas
#The OFFICIAL Repo of this is - https://github.com/Justagwas/Media-Downloader
import tkinter as tk
from tkinter import messagebox, ttk
from yt_dlp import YoutubeDL
import threading
import os
import sys
import time
import queue
import logging
import requests
import shutil
import zipfile
import subprocess
from urllib.parse import urlparse
import ctypes as ct
from packaging.version import Version, InvalidVersion
from pathvalidate import sanitize_filename

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

import win32event, win32api, winerror

mutex = win32event.CreateMutex(None, False, "MediaDownloaderMutex")
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    sys.exit()

class MediaDownloader:
    def set_controls_state(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.paste_button.config(state=state)
        self.url_entry.config(state=state)
        for btn in self.format_buttons.values():
            btn.config(state=state)
        for btn in self.quality_buttons.values():
            btn.config(state=state)
        self.download_button.config(state=state)
    def add_hover_effect(self, btn, *, is_selected_func=None, is_enabled_func=None, bg_normal="#232526", fg_normal="#e6e6e6", bg_hover="#31363b", fg_hover="#80cfff", bg_selected="#0078d4", fg_selected="#fff", bg_disabled="#232526", fg_disabled="#888888", is_hover_enabled_func=None):
        def on_enter(e):
            if is_hover_enabled_func and not is_hover_enabled_func():
                return
            if (is_selected_func and is_selected_func()):
                return
            if (is_enabled_func and not is_enabled_func()):
                return
            btn.config(bg=bg_hover, fg=fg_hover)
        def on_leave(e):
            if is_enabled_func and not is_enabled_func():
                btn.config(bg=bg_disabled, fg=fg_disabled)
            elif is_selected_func and is_selected_func():
                btn.config(bg=bg_selected, fg=fg_selected)
            else:
                btn.config(bg=bg_normal, fg=fg_normal)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def __init__(self, root):
        self.root = root
        self.center_window(480, 380)
        self.root.title("Media Downloader v1.2.0")
        self.root.geometry("480x380")
        self.root.configure(bg="#181a1b")
        self.root.resizable(False, False)
        self.download_thread = None
        self.ydl = None
        self.status_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.gui_queue = queue.Queue()
        self.splash_frame = None
        self.main_frame = None
        self.progress = None
        self.console = None
        self.downloading = False
        self.status_polling = True
        self.status_poll_thread = threading.Thread(target=self.poll_status_queue, daemon=True)
        self.status_poll_thread.start()
        self.show_splash()
        self.root.after(100, self.deferred_startup)

    def center_window(self, width, height):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = int((screen_width / 2) - (width / 2))
        y = int((screen_height / 2) - (height / 2))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def show_splash(self):
        self.splash_frame = tk.Frame(self.root, bg="#313131")
        self.splash_frame.pack(fill="both", expand=True)
        label = tk.Label(self.splash_frame, text="Media Downloader", font=("Segoe UI", 18, "bold"), fg="#FFFFFF", bg="#313131")
        label.pack(pady=40)
        sub = tk.Label(self.splash_frame, text="Loading, please wait...", font=("Segoe UI", 12), fg="#FFFFFF", bg="#313131")
        sub.pack(pady=10)
        self.progress = ttk.Progressbar(self.splash_frame, mode="indeterminate", length=250, style="WhiteOnBlack.Horizontal.TProgressbar")
        self.progress.pack(pady=20)
        self.progress.start(10)

    def deferred_startup(self):
        def startup_tasks():
            self.set_icon()
            def after_ffmpeg():
                self.check_for_updates()
                self.root.after(0, self.show_main_ui)
            def ffmpeg_callback():
                after_ffmpeg()
            self._ffmpeg_callback = ffmpeg_callback
            self.check_ffmpeg()
        threading.Thread(target=startup_tasks, daemon=True).start()

    def show_main_ui(self):
        if self.splash_frame:
            self.splash_frame.destroy()
        self.create_widgets()

    def set_icon(self):
        script_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
        icon_path = os.path.join(script_dir, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
                return
            except Exception as e:
                logging.error(f"Failed to set application icon: {e}")
        def is_admin():
            try: return ct.windll.shell32.IsUserAnAdmin()
            except: return False
        def run_as_admin():
            try:
                exe = os.path.abspath(sys.argv[0])
                params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
                ct.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{exe}" {params}', None, 1)
                os._exit(0)
            except Exception as e:
                logging.error(f"Failed to relaunch as admin: {e}")
                self.gui_queue.put(lambda: messagebox.showerror("Error", "Failed to request administrator privileges."))
                return False
        if messagebox.askyesno("Download Icon", "The application's icon is missing. Would you like to download and install it?"):
            if not is_admin():
                if not run_as_admin(): return
            try:
                icon_url = "https://github.com/Justagwas/Media-Downloader/raw/master/Media-Downloader/icon.ico"
                logging.info(f"Downloading icon from {icon_url} to {icon_path}")
                response = requests.get(icon_url, stream=True, timeout=10)
                with open(icon_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk: file.write(chunk)
                self.root.iconbitmap(icon_path)
            except Exception as e:
                logging.error(f"Failed to download or set application icon: {e}")
                messagebox.showerror("Error", "Failed to download or set the application's icon.")

    def check_ffmpeg(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_path = os.path.join(script_dir, "ffmpeg.exe")
        ffmpeg_in_script_dir = os.path.exists(ffmpeg_path)
        ffmpeg_in_path = self.is_ffmpeg_installed()
        if not ffmpeg_in_script_dir and not ffmpeg_in_path:
            self.root.after(0, lambda: self.prompt_ffmpeg_download(callback=getattr(self, '_ffmpeg_callback', None)))
        else:
            if hasattr(self, '_ffmpeg_callback') and self._ffmpeg_callback:
                self.root.after(0, self._ffmpeg_callback)

    def is_ffmpeg_installed(self):
        import os
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_path = os.path.join(script_dir, "ffmpeg.exe")
        if os.path.isfile(ffmpeg_path):
            return True
        try:
            result = subprocess.run(["ffmpeg"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
            combined = (result.stdout or "") + (result.stderr or "")
            if "not recognized" in combined or "is not recognized" in combined:
                return False
            return True
        except Exception:
            return

    def prompt_ffmpeg_download(self, callback=None):
        bg_main = "#181a1b"
        fg_label = "#e6e6e6"
        bg_button = "#232526"
        fg_button = "#e6e6e6"
        active_bg_button = "#31363b"
        active_fg_button = "#80cfff"

        def on_confirm():
            if messagebox.askyesno(
                "FFmpeg Not Installed",
                "If you don't install FFmpeg, there's a high chance the application won't work.\n\nAre you sure you want to continue without installing FFmpeg?"
            ):
                self.clear_ffmpeg_prompt(callback)
            else:
                self.prompt_ffmpeg_download(callback)

        def on_download_choice():
            for widget in self.root.winfo_children():
                widget.destroy()

            tk.Label(
                self.root,
                text="Choose how to download FFmpeg:",
                bg=bg_main,
                fg=fg_label,
                wraplength=420,
                font=("Segoe UI", 12, "bold"),
                justify="center"
            ).pack(pady=10)

            tk.Label(
                self.root,
                text="Automatic (Recommended): The application will download and install FFmpeg after you are introduced to the legal disclaimer.\n\n"
                     "Manual: Follow the steps to download and install FFmpeg yourself.",
                bg=bg_main,
                fg=fg_label,
                wraplength=420,
                justify="left",
                font=("Segoe UI", 10)
            ).pack(pady=10)

            button_frame = tk.Frame(self.root, bg=bg_main)
            button_frame.pack(pady=10)

            auto_button = tk.Button(
                button_frame, text="Automatic", command=show_legal_disclaimer,
                font=("Segoe UI", 11, "bold"),
                bg=bg_button, fg=fg_button,
                activebackground=active_bg_button, activeforeground=active_fg_button,
                relief="flat", bd=0, padx=12, pady=2, width=12
            )
            auto_button.pack(side=tk.LEFT, padx=5)
            self.add_hover_effect(auto_button, bg_normal=bg_button, fg_normal=fg_button, bg_hover=active_bg_button, fg_hover=active_fg_button)
            manual_button = tk.Button(
                button_frame, text="Manual", command=show_manual_steps,
                font=("Segoe UI", 11, "bold"),
                bg=bg_button, fg=fg_button,
                activebackground=active_bg_button, activeforeground=active_fg_button,
                relief="flat", bd=0, padx=12, pady=2, width=12
            )
            manual_button.pack(side=tk.LEFT, padx=5)
            self.add_hover_effect(manual_button, bg_normal=bg_button, fg_normal=fg_button, bg_hover=active_bg_button, fg_hover=active_fg_button)

        def show_legal_disclaimer():
            for widget in self.root.winfo_children():
                widget.destroy()

            tk.Label(
                self.root,
                text="Legal Disclaimer:",
                bg=bg_main,
                fg=fg_label,
                font=("Segoe UI", 12, "bold"),
                justify="center"
            ).pack(pady=10)

            tk.Label(
                self.root,
                text="By proceeding, you acknowledge that FFmpeg is a third-party software.\n\n"
                     "The application will download FFmpeg from an official Windows build.\n\n"
                     "FFmpeg is licensed under the GNU Lesser General Public License (LGPL) version 2.1 or later.\n"
                     "For more details, visit:",
                bg=bg_main,
                fg=fg_label,
                wraplength=420,
                justify="left",
                font=("Segoe UI", 10)
            ).pack(pady=0)
            link = tk.Label(
                self.root,
                text="https://ffmpeg.org/legal.html",
                bg=bg_main,
                fg="blue",
                cursor="hand2",
                wraplength=220,
                justify="left",
                anchor="w",
                font=("Segoe UI", 10, "underline")
            )
            link.pack(pady=5, padx=38, anchor="w")
            link.bind("<Button-1>", lambda e: os.startfile("https://ffmpeg.org/legal.html"))

            button_frame = tk.Frame(self.root, bg=bg_main)
            button_frame.pack(pady=10)

            self.proceed_button = tk.Button(
                button_frame, text="Proceed", command=lambda: [self.proceed_button.config(state=tk.DISABLED), on_download()],
                font=("Segoe UI", 11, "bold"),
                bg=bg_button, fg=fg_button,
                activebackground=active_bg_button, activeforeground=active_fg_button,
                relief="flat", bd=0, padx=12, pady=2, width=12
            )
            self.proceed_button.pack(side=tk.LEFT, padx=5)
            self.add_hover_effect(self.proceed_button, bg_normal=bg_button, fg_normal=fg_button, bg_hover=active_bg_button, fg_hover=active_fg_button)
            cancel_button = tk.Button(
                button_frame, text="Cancel", command=self.abort,
                font=("Segoe UI", 11, "bold"),
                bg="#2d2323", fg="#ff6b6b",
                activebackground="#3a2323", activeforeground="#ffbaba",
                relief="flat", bd=0, padx=12, pady=2, width=12
            )
            cancel_button.pack(side=tk.LEFT, padx=5)
            self.add_hover_effect(cancel_button, bg_normal="#2d2323", fg_normal="#ff6b6b", bg_hover="#472424", fg_hover="#ffbaba")

        def show_manual_steps():
            for widget in self.root.winfo_children():
                widget.destroy()

            tk.Label(
                self.root,
                text="Manual Download Steps:",
                bg=bg_main,
                fg=fg_label,
                font=("Segoe UI", 12, "bold"),
                justify="center"
            ).pack(pady=10)

            tk.Label(
                self.root,
                text="1. Visit the official FFmpeg build page:",
                bg=bg_main,
                fg=fg_label,
                wraplength=420,
                justify="left",
                font=("Segoe UI", 10)
            ).pack(pady=0, padx=50, anchor="w")

            link = tk.Label(
                self.root,
                text="https://github.com/GyanD/codexffmpeg/releases/latest",
                bg=bg_main,
                fg="blue",
                cursor="hand2",
                wraplength=420,
                justify="left",
                anchor="w",
                font=("Segoe UI", 10, "underline")
            )
            link.pack(pady=0, padx=50, anchor="w")
            link.bind("<Button-1>", lambda e: os.startfile("https://github.com/GyanD/codexffmpeg/releases/latest"))

            tk.Label(
                self.root,
                text="2. Download the file named 'ffmpeg-x.x.x-essentials_build.zip'.\n"
                     "3. Extract the downloaded ZIP file.\n"
                     "4. Locate the 'ffmpeg.exe' file within the extracted folder and its subfolders.\n"
                     "5. Move the 'ffmpeg.exe' file to the same directory as this application.",
                bg=bg_main,
                fg=fg_label,
                wraplength=420,
                justify="left",
                font=("Segoe UI", 10)
            ).pack(pady=5)

            tk.Label(
                self.root,
                text="Once you have completed these steps, restart the application.",
                bg=bg_main,
                fg=fg_label,
                wraplength=420,
                justify="left",
                font=("Segoe UI", 10, "italic")
            ).pack(pady=10)

            ok_button = tk.Button(
                self.root, text="OK", command=self.abort,
                font=("Segoe UI", 11, "bold"),
                bg=bg_button, fg=fg_button,
                activebackground=active_bg_button, activeforeground=active_fg_button,
                relief="flat", bd=0, padx=12, pady=2, width=12
            )
            ok_button.pack(pady=10)
            self.add_hover_effect(ok_button, bg_normal=bg_button, fg_normal=fg_button, bg_hover=active_bg_button, fg_hover=active_fg_button)

        def on_download():
            def download_ffmpeg():
                try:
                    self.set_status("Downloading FFmpeg... (DO NOT CLOSE APPLICATION)")
                    download_url = "https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip"
                    script_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
                    download_path = os.path.join(script_dir, "ffmpeg-essentials.zip")
                    extract_path = os.path.join(script_dir, "ffmpeg_temp")

                    logging.info(f"Downloading FFmpeg from {download_url} to {download_path}")
                    response = requests.get(download_url, stream=True)
                    with open(download_path, "wb") as file:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                file.write(chunk)

                    self.set_status("Extracting FFmpeg...")
                    logging.info(f"Extracting FFmpeg to {extract_path}")
                    os.makedirs(extract_path, exist_ok=True)
                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)

                    bin_folder = next(
                        (os.path.join(root, "ffmpeg.exe") for root, _, files in os.walk(extract_path) if "ffmpeg.exe" in files),
                        None
                    )
                    if bin_folder:
                        shutil.copy(bin_folder, script_dir)
                        logging.info(f"Copied ffmpeg.exe to {script_dir}")

                    os.remove(download_path)
                    shutil.rmtree(extract_path)

                    self.set_status("FFmpeg installed successfully!")
                    self.root.after(0, lambda: messagebox.showinfo("Success", "FFmpeg has been installed successfully."))
                    self.root.after(0, self.clear_ffmpeg_prompt)
                except Exception as e:
                    self.set_status("FFmpeg installation failed.")
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to download and install FFmpeg: {e}"))
            threading.Thread(target=download_ffmpeg, daemon=True).start()

        for widget in self.root.winfo_children():
            widget.destroy()
        message = (
            "The FFmpeg framework, which is essential for this application to function, is missing from your system.\n\n"
            "Without this dependency, the application will not work.\n\n"
            "Would you like to download and install FFmpeg now?"
        )
        tk.Label(self.root, text=message, bg=bg_main, fg=fg_label, wraplength=420, justify="left", font=("Segoe UI", 10)).pack(pady=10)

        button_frame = tk.Frame(self.root, bg=bg_main)
        button_frame.pack(pady=10)

        proceed_button = tk.Button(button_frame, text="Yes", command=on_download_choice,
                                  font=("Segoe UI", 11, "bold"),
                                  bg=bg_button, fg=fg_button,
                                  activebackground=active_bg_button, activeforeground=active_fg_button,
                                  relief="flat", bd=0, padx=12, pady=2, width=12)
        proceed_button.pack(side=tk.LEFT, padx=5)
        self.add_hover_effect(proceed_button, bg_normal=bg_button, fg_normal=fg_button, bg_hover=active_bg_button, fg_hover=active_fg_button)
        confirm_button = tk.Button(button_frame, text="Cancel", command=on_confirm,
                                  font=("Segoe UI", 11, "bold"),
                                  bg="#2d2323", fg="#ff6b6b",
                                  activebackground="#3a2323", activeforeground="#ffbaba",
                                  relief="flat", bd=0, padx=12, pady=2, width=12)
        confirm_button.pack(side=tk.LEFT, padx=5)
        self.add_hover_effect(confirm_button, bg_normal="#2d2323", fg_normal="#ff6b6b", bg_hover="#472424", fg_hover="#ffbaba")

    def clear_ffmpeg_prompt(self, callback=None):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.create_widgets()
        if callback:
            callback()

    def create_widgets(self):
        if self.main_frame:
            self.main_frame.destroy()
        for widget in self.root.winfo_children():
            widget.destroy()

        outer = tk.Frame(self.root, bg="#181a1b")
        outer.pack(fill="both", expand=True)
        outer.grid_propagate(False)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        self.main_frame = tk.Frame(outer, bg="#181a1b", padx=32, pady=24)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.grid_propagate(False)
        self.main_frame.grid_rowconfigure(6, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        url_row = tk.Frame(self.main_frame, bg="#181a1b")
        url_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        self.url_entry = tk.Entry(url_row, font=("Segoe UI", 12), bg="#232526", fg="#e6e6e6", insertbackground="#e6e6e6", relief="flat", bd=2, highlightthickness=1.5, highlightbackground="#31363b", highlightcolor="#0078d4")
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipadx=6, ipady=6)
        self.paste_button = tk.Button(url_row, text="Paste", command=self.paste_url, font=("Segoe UI", 11, "bold"), bg="#232526", fg="#e6e6e6", activebackground="#31363b", activeforeground="#80cfff", relief="flat", bd=0, highlightthickness=1.5, highlightbackground="#31363b", padx=12, pady=2, width=10)
        self.paste_button.pack(side=tk.LEFT, padx=(8, 0), ipadx=0, ipady=2)
        self.add_hover_effect(
            self.paste_button,
            is_hover_enabled_func=lambda: not self.downloading
        )

        self.format_options = [
            ("mp4", "MP4"),
            ("mp3", "MP3"),
            ("mov", "MOV"),
            ("wav", "WAV")
        ]
        self.selected_format = tk.StringVar(value="mp4")
        self._prev_format = "mp4"
        format_row = tk.Frame(self.main_frame, bg="#181a1b")
        format_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        self.format_buttons = {}
        for fmt, label in self.format_options:
            btn = tk.Button(
                format_row, text=label, font=("Segoe UI", 11, "bold"),
                bg="#232526", fg="#e6e6e6", activebackground="#31363b", activeforeground="#80cfff",
                relief="flat", bd=0, width=10, height=1,
                command=lambda f=fmt: self.try_format_change(f)
            )
            btn.pack(side=tk.LEFT, padx=4, ipadx=0, ipady=2)
            self.add_hover_effect(
                btn,
                is_selected_func=lambda fmt=fmt: self.selected_format.get() == fmt,
                is_enabled_func=lambda: True,
                is_hover_enabled_func=lambda: not self.downloading
            )
            self.format_buttons[fmt] = btn
        self.update_format_buttons()

        self.quality_options = [
            ("BEST QUALITY", "BEST"),
            ("2160p", "2160p"),
            ("1440p", "1440p"),
            ("1080p", "1080p"),
            ("720p", "720p"),
            ("480p", "480p"),
            ("360p", "360p"),
            ("240p", "240p"),
            ("144p", "144p")
        ]
        self.selected_quality = tk.StringVar(value="BEST QUALITY")
        self._prev_quality = "BEST QUALITY"
        quality_row = tk.Frame(self.main_frame, bg="#181a1b")
        quality_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        self.quality_buttons = {}
        best_qual, best_label = self.quality_options[0]
        best_btn = tk.Button(
            quality_row, text=best_label, font=("Segoe UI", 11, "bold"),
            bg="#232526", fg="#e6e6e6", activebackground="#31363b", activeforeground="#80cfff",
            relief="flat", bd=0, width=8, height=1,
            command=lambda q=best_qual: self.try_quality_change(q)
        )
        best_btn.pack(side=tk.LEFT, padx=(0, 2), ipadx=0, ipady=2)
        self.add_hover_effect(
            best_btn,
            is_selected_func=lambda: self.selected_quality.get() == best_qual,
            is_enabled_func=lambda: self.selected_format.get() not in ("mp3", "wav"),
            is_hover_enabled_func=lambda: not self.downloading
        )
        self.quality_buttons[best_qual] = best_btn
        canvas_frame = tk.Frame(quality_row, bg="#181a1b")
        canvas_frame.pack(side=tk.LEFT, fill="x", expand=True)
        self.quality_canvas = tk.Canvas(canvas_frame, bg="#181a1b", highlightthickness=0, height=33)
        self.quality_canvas.pack(side=tk.LEFT, fill="x", expand=True)
        self.quality_scroll = tk.Scrollbar(canvas_frame, orient="horizontal", command=self.quality_canvas.xview)
        self.quality_scroll.pack(side=tk.BOTTOM, fill="x")
        self.quality_canvas.configure(xscrollcommand=self.quality_scroll.set)
        self.quality_inner = tk.Frame(self.quality_canvas, bg="#181a1b")
        self.quality_canvas.create_window((0, 0), window=self.quality_inner, anchor="nw")
        for qual, label in self.quality_options[1:]:
            btn = tk.Button(
                self.quality_inner, text=label, font=("Segoe UI", 11, "bold"),
                bg="#232526", fg="#e6e6e6", activebackground="#31363b", activeforeground="#80cfff",
                relief="flat", bd=0, width=8, height=1,
                command=lambda q=qual: self.try_quality_change(q)
            )
            btn.pack(side=tk.LEFT, padx=2, ipadx=0, ipady=2)
            self.add_hover_effect(
                btn,
                is_selected_func=lambda qual=qual: self.selected_quality.get() == qual,
                is_enabled_func=lambda: self.selected_format.get() not in ("mp3", "wav"),
                is_hover_enabled_func=lambda: not self.downloading
            )
            self.quality_buttons[qual] = btn
        self.quality_inner.update_idletasks()
        self.quality_canvas.config(scrollregion=self.quality_canvas.bbox("all"))
        def _on_quality_mousewheel(event):
            if event.delta:
                self.quality_canvas.xview_scroll(int(-1*(event.delta/120)), "units")
            elif event.num == 5:
                self.quality_canvas.xview_scroll(1, "units")
            elif event.num == 4:
                self.quality_canvas.xview_scroll(-1, "units")
        def _bind_quality_scroll(_):
            self.quality_canvas.bind_all("<MouseWheel>", _on_quality_mousewheel)
            self.quality_canvas.bind_all("<Shift-MouseWheel>", _on_quality_mousewheel)
            self.quality_canvas.bind_all("<Button-4>", _on_quality_mousewheel)
            self.quality_canvas.bind_all("<Button-5>", _on_quality_mousewheel)
        def _unbind_quality_scroll(_):
            self.quality_canvas.unbind_all("<MouseWheel>")
            self.quality_canvas.unbind_all("<Shift-MouseWheel>")
            self.quality_canvas.unbind_all("<Button-4>")
            self.quality_canvas.unbind_all("<Button-5>")
        self.quality_canvas.bind("<Enter>", _bind_quality_scroll)
        self.quality_canvas.bind("<Leave>", _unbind_quality_scroll)
        self.update_quality_buttons()
        btn_row = tk.Frame(self.main_frame, bg="#181a1b")
        btn_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        self.download_button = tk.Button(
            btn_row, text="Download", command=self.start_download, font=("Segoe UI", 11, "bold"),
            bg="#222c24", fg="#4BA85D", activebackground="#1F3824", activeforeground="#fff",
            relief="flat", bd=0, highlightthickness=1.5, highlightbackground="#145c2c", padx=0, pady=2, width=16
        )
        self.download_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipadx=0, ipady=2)
        self.add_hover_effect(
            self.download_button,
            bg_normal="#222c24", fg_normal="#5AD172",
            bg_hover="#2A5032", fg_hover="#95FFAA",
            is_hover_enabled_func=lambda: not self.downloading
        )
        self.abort_button = tk.Button(
            btn_row, text="Terminate", command=self.abort, font=("Segoe UI", 11, "bold"),
            bg="#2d2323", fg="#ff6b6b", activebackground="#3a2323", activeforeground="#ffbaba",
            relief="flat", bd=0, highlightthickness=1.5, highlightbackground="#6b2323", padx=0, pady=2, width=16
        )
        self.abort_button.pack(side=tk.LEFT, fill=tk.X, expand=True, ipadx=0, ipady=2)
        self.add_hover_effect(self.abort_button, bg_normal="#2d2323", fg_normal="#ff6b6b", bg_hover="#472424", fg_hover="#ffbaba", is_hover_enabled_func=None)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#181a1b")
        style.configure("TLabel", background="#181a1b", foreground="#e6e6e6")
        style.configure("WhiteOnBlack.TCombobox",
            fieldbackground="#232526",
            background="#232526",
            foreground="#e6e6e6",
            selectforeground="#e6e6e6",
            selectbackground="#31363b",
            arrowcolor="#e6e6e6",
            bordercolor="#31363b",
            borderwidth=1.5,
            padding=6
        )
        style.map("WhiteOnBlack.TCombobox",
            fieldbackground=[('readonly', '#232526')],
            background=[('readonly', '#232526')],
            foreground=[('readonly', '#e6e6e6')],
            selectbackground=[('readonly', '#31363b')],
            selectforeground=[('readonly', '#e6e6e6')],
            arrowcolor=[('readonly', '#e6e6e6')],
        )
        style.configure("Modern.Horizontal.TProgressbar", troughcolor="#232526", bordercolor="#31363b", background="#0078d4", lightcolor="#0078d4", darkcolor="#0078d4", thickness=18)
        style.layout("Modern.Horizontal.TProgressbar",
            [('Horizontal.Progressbar.trough',
              {'children': [('Horizontal.Progressbar.pbar',
                             {'side': 'left', 'sticky': 'ns'})],
               'sticky': 'nswe'})]
        )

        self.progress = ttk.Progressbar(self.main_frame, mode="determinate", length=380, style="Modern.Horizontal.TProgressbar")
        self.progress.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.progress["value"] = 0

        self.console = tk.Text(self.main_frame, height=4, bg="#232323", fg="#e6e6e6", insertbackground="#e6e6e6", state="disabled", wrap="word", font=("Cascadia Mono", 10))
        self.console.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(0, 0))

        self.main_frame.grid_rowconfigure(6, weight=1)

    def update_format_buttons(self):
        for fmt, btn in self.format_buttons.items():
            if self.selected_format.get() == fmt:
                btn.config(bg="#0078d4", fg="#fff")
            else:
                btn.config(bg="#232526", fg="#e6e6e6")

    def update_quality_buttons(self):
        is_audio = self.selected_format.get() in ("mp3", "wav")
        for qual, btn in self.quality_buttons.items():
            if is_audio:
                btn.config(state="disabled", bg="#232526", fg="#888888")
            else:
                btn.config(state="normal")
                if self.selected_quality.get() == qual:
                    btn.config(bg="#0078d4", fg="#fff")
                else:
                    btn.config(bg="#232526", fg="#e6e6e6")

    def try_format_change(self, fmt):
        prev_fmt = self.selected_format.get()
        self._prev_format = prev_fmt
        if fmt in ("mov", "wav") and fmt != prev_fmt:
            if not self.prompt_format_confirmation(fmt):
                return
        self.selected_format.set(fmt)
        if fmt not in ("mp3", "wav"):
            if self.selected_quality.get() not in [q[0] for q in self.quality_options]:
                self.selected_quality.set("BEST QUALITY")
        self.update_format_buttons()
        self.update_quality_buttons()

    def try_quality_change(self, qual):
        prev_qual = self.selected_quality.get()
        self._prev_quality = prev_qual
        if qual != prev_qual:
            if not self.prompt_quality_change(qual):
                return
        self.selected_quality.set(qual)
        self.update_quality_buttons()

    def paste_url(self):
        try:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, self.root.clipboard_get())
            self._fade_entry_fg(self.url_entry, start_color="#2196f3", end_color="#e6e6e6", steps=10, delay=40)
        except tk.TclError:
            messagebox.showerror("Error", "No URL found in clipboard")

    def _fade_entry_fg(self, entry, start_color, end_color, steps=10, delay=40):
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        def rgb_to_hex(rgb):
            return '#{:02x}{:02x}{:02x}'.format(*rgb)
        start_rgb = hex_to_rgb(start_color)
        end_rgb = hex_to_rgb(end_color)
        def step(i):
            ratio = i / steps
            curr_rgb = tuple(
                int(start_rgb[j] + (end_rgb[j] - start_rgb[j]) * ratio)
                for j in range(3)
            )
            entry.config(fg=rgb_to_hex(curr_rgb))
            if i < steps:
                entry.after(delay, lambda: step(i+1))
        step(0)


    def sanitize_filename(self, name):
        return sanitize_filename(name).strip()


    def sanitize_url(self, url):
        return url if urlparse(url).netloc else None


    def prompt_quality_change(self, selected_quality):
        if selected_quality != "BEST QUALITY":
            result = messagebox.askyesno(
                "Quality Format Change",
                "The provided media URL might not support other formats. Do you want to proceed?")
            if not result:
                self.selected_quality.set(self._prev_quality)
                self.update_quality_buttons()
                return False
        return True


    def prompt_format_confirmation(self, selected_format):
        if selected_format in ("mp4", "mp3"): return True
        result = messagebox.askyesno(
            "Format Download Warning",
            f"Downloading {selected_format} may take significantly longer than MP4/MP3.\nDo you want to continue?")
        if not result:
            self.selected_format.set(self._prev_format)
            self.update_format_buttons()
            self.update_quality_buttons()
            return False
        return True

    def start_download(self):
        if self.progress:
            self.progress["value"] = 0
            style = ttk.Style(self.root)
            style.configure("Modern.Horizontal.TProgressbar", background="#0078d4", lightcolor="#0078d4", darkcolor="#0078d4")
            self.progress.update_idletasks()
        if self.console:
            self.console.config(state="normal")
            self.console.delete(1.0, tk.END)
            self.console.config(state="disabled")

        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a media URL")
            return

        sanitized_url = self.sanitize_url(url)
        if not sanitized_url:
            messagebox.showerror("Error", "Please enter a valid media URL")
            return
        format_choice = self.selected_format.get()
        if not format_choice:
            messagebox.showerror("Error", "Please select a format")
            return
        quality_choice = self.selected_quality.get()
        if format_choice in ("mp3", "wav"):
            quality_choice = "BEST QUALITY"
        self.set_controls_state(False)
        self.download_button.config(state=tk.DISABLED)
        self.downloading = True
        self.poll_progress_queue()
        def check_and_download():
            self.append_console("Checking media info...\n")
            downloads_dir = os.path.expanduser('~/Downloads')
            media_dl_dir = os.path.join(downloads_dir, 'Media-Downloader')
            os.makedirs(media_dl_dir, exist_ok=True)
            try:
                ydl_opts = {
                    'quiet': True,
                    'skip_download': True,
                    'no_warnings': True,
                    'simulate': True,
                }
                with YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(sanitized_url, download=False)
                title = info_dict.get('title', '')
                sanitized_title = self.sanitize_filename(title)
                sanitized_title = ''.join(c for c in sanitized_title if c.isalnum() or c in (' ', '.', '_', '-')).strip()
                if not sanitized_title:
                    sanitized_title = 'media_file'
                final_filename = f"{sanitized_title}.{format_choice}"
                output_path_final = os.path.join(media_dl_dir, final_filename)
                if os.path.exists(output_path_final):
                    self.append_console(f"File already exists: {output_path_final}\n")
                    def ask_redownload():
                        if messagebox.askyesno("File Exists", f"File already exists:\n{output_path_final}\nDo you want to download it again?"):
                            self.download_thread = threading.Thread(target=self.download_video, args=(sanitized_url, format_choice, quality_choice, sanitized_title))
                            self.download_thread.start()
                        else:
                            self.append_console("Aborted!\n")
                            self.downloading = False
                            self.set_controls_state(True),
                            self.download_button.config(state=tk.NORMAL)

                    self.root.after(0, ask_redownload)
                    return
            except Exception as e:
                self.append_console("Failed to retrieve media info!\n")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to retrieve media info: {e}"))
                self.root.after(0, lambda: [
                    self.set_controls_state(True),
                    self.download_button.config(state=tk.NORMAL)
                ])
                return
            self.download_thread = threading.Thread(target=self.download_video, args=(sanitized_url, format_choice, quality_choice, sanitized_title))
            self.download_thread.start()

        threading.Thread(target=check_and_download, daemon=True).start()


    def abort(self):
        if self.ydl:
            self.ydl.download = False
            self.append_console("Download aborted!\n")
        try:
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            subprocess.run([
                "taskkill", "/F", "/IM", "ffmpeg.exe"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo, creationflags=creationflags)
        except Exception:
            pass
        self.terminate_program()

    def terminate_program(self):
        self.status_polling = False
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def download_video(self, url, format_choice, quality_choice, sanitized_title):
        self.display_percent_in_console(0)
        self.append_console("Starting download...\n")
        downloads_dir = os.path.expanduser('~/Downloads')
        media_dl_dir = os.path.join(downloads_dir, 'Media-Downloader')
        os.makedirs(media_dl_dir, exist_ok=True)
        final_filename = f"{sanitized_title}.{format_choice}"
        output_path_final = os.path.join(media_dl_dir, final_filename)
        output_template = os.path.join(media_dl_dir, f'{sanitized_title}_TEMP.%(ext)s')

        quality_format = {
            "BEST QUALITY": "bestvideo+bestaudio/best",
            "144p": "worstvideo[height<=144]+bestaudio/best[height<=144]",
            "240p": "worstvideo[height<=240]+bestaudio/best[height<=240]",
            "360p": "worstvideo[height<=360]+bestaudio/best[height<=360]",
            "480p": "worstvideo[height<=480]+bestaudio/best[height<=480]",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
            "2160p (4k)": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        }

        windows_hide_flag = True
        if format_choice in ['mp3', 'wav']:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'progress_hooks': [self.ydl_hook],
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': format_choice,
                    'preferredquality': '0',
                }],
                'concurrent_fragment_downloads': 8,
                'external_downloader_args': {
                    'aria2c': ['-x', '16', '-j', '16']
                },
                'external_downloader': 'aria2c',
                'quiet': True,
                'windows_hide': windows_hide_flag,
            }
        else:
            ydl_opts = {
                'format': quality_format.get(quality_choice, 'best'),
                'outtmpl': output_template,
                'progress_hooks': [self.ydl_hook],
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mov',
                    'ffmpeg_args': ['-preset', 'ultrafast'],
                }] if format_choice == 'mov' else [],
                'concurrent_fragment_downloads': 8,
                'external_downloader_args': {
                    'aria2c': ['-x', '16', '-j', '16']
                },
                'external_downloader': 'aria2c',
                'quiet': True,
                'windows_hide': windows_hide_flag,
            }

        start_time = time.time()
        with YoutubeDL(ydl_opts) as ydl:
            self.ydl = ydl
            try:
                ydl.download([url])
                temp_files = [f for f in os.listdir(media_dl_dir) if f.startswith(sanitized_title) and '_TEMP.' in f]
                for temp_file in temp_files:
                    temp_path = os.path.join(media_dl_dir, temp_file)
                    final_path = os.path.join(media_dl_dir, final_filename)
                    if os.path.exists(final_path):
                        try:
                            os.remove(final_path)
                        except Exception:
                            pass
                    os.rename(temp_path, final_path)
                if self.progress:
                    style = ttk.Style(self.root)
                    style.configure("Modern.Horizontal.TProgressbar", background="#4BA85D", lightcolor="#4BA85D", darkcolor="#4BA85D")
                    self.progress["value"] = 100
                    self.progress.update_idletasks()
                elapsed = time.time() - start_time
                file_size = os.path.getsize(output_path_final) if os.path.exists(output_path_final) else 0
                size_mb = file_size / (1024 * 1024)
                self.append_console(f"Download completed successfully!\nSaved as: {output_path_final}\nFile size: {size_mb:.2f} MB\nTime taken: {elapsed:.2f} seconds\n")
            except Exception as e:
                if 'abort' in str(e).lower():
                    self.append_console("Download aborted!\n")
                else:
                    self.append_console("Download failed!\n")
                    self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.downloading = False
                self.root.after(0, lambda: self.set_controls_state(True))

    def ydl_hook(self, d):
        if d['status'] == 'downloading':
            try:
                percent_str = d.get('_percent_str', '').strip()
                percent = percent_str.split('%')[0].strip()[-4:]
                try:
                    val = float(percent)
                except Exception:
                    val = 0
                self.progress_queue.put(val)
            except Exception:
                self.progress_queue.put(0)
        elif d['status'] == 'finished':
            self.progress_queue.put(100)


    def check_for_updates(self):
        def update_check():
            try:
                current_version = "v1.2.0"
                releases_url = "https://api.github.com/repos/Justagwas/Media-Downloader/releases/latest"
                response = requests.get(releases_url, timeout=10)
                if response.status_code == 200:
                    latest_release = response.json()
                    latest_version = latest_release.get("tag_name", "")
                    try:
                        if Version(latest_version) > Version(current_version):
                            download_url = "https://github.com/Justagwas/Media-Downloader/releases/latest/download/Media_Downloader_Setup.exe"
                            prompt_message = (
                                f"A newer version - {latest_version} is available!\n"
                                f"Would you like to download it now?"
                            )
                            self.gui_queue.put(lambda: self._prompt_update(prompt_message, download_url))
                    except InvalidVersion:
                        logging.error(f"Invalid version format: {latest_version}")
                else:
                    logging.error(f"Failed to fetch release info: HTTP {response.status_code}")
            except requests.RequestException as e:
                logging.error(f"Network error during update check: {e}")
                self.gui_queue.put(lambda: messagebox.showerror("Update Check Failed", "Unable to check for updates. Please try again later."))

        threading.Thread(target=update_check, daemon=True).start()

    def _prompt_update(self, prompt_message, download_url):
        if messagebox.askyesno("Update Available", prompt_message):
            os.startfile(download_url)
            self.abort()

    def poll_status_queue(self):
        while self.status_polling:
            try:
                while True:
                    msg = self.status_queue.get_nowait()
                    self.append_console(msg + "\n")
            except queue.Empty:
                pass
            time.sleep(0.1)

    def poll_progress_queue(self):
        if not self.downloading:
            return
        try:
            while True:
                val = self.progress_queue.get_nowait()
                self.display_percent_in_console(val)
        except queue.Empty:
            pass
        if self.downloading:
            self.root.after(100, self.poll_progress_queue)

    def set_status(self, msg):
        self.status_queue.put(msg)

    def append_console(self, msg):
        if self.console:
            self.console.config(state="normal")
            self.console.insert(tk.END, msg)
            lines = int(self.console.index('end-1c').split('.')[0])
            if lines > 200:
                self.console.delete("1.0", f"{lines-199}.0")
            self.console.see(tk.END)
            self.console.config(state="disabled")

    def display_percent_in_console(self, percent):
        if self.console:
            self.console.config(state="normal")
            content = self.console.get("1.0", tk.END)
            lines = content.rstrip("\n").split("\n")
            if percent == 100:
                if lines and lines[-1].strip().endswith("% Done"):
                    lines = lines[:-1]
                lines.append("Process finished.")
            else:
                percent_line = f"{percent}% Done"
                if lines and lines[-1].strip().endswith("% Done"):
                    lines = lines[:-1]
                lines.append(percent_line)
            self.console.delete("1.0", tk.END)
            self.console.insert(tk.END, "\n".join(lines) + ("\n" if lines else ""))
            self.console.see(tk.END)
            self.console.config(state="disabled")
        if self.progress:
            try:
                self.progress["value"] = float(percent)
                self.progress.update_idletasks()
            except Exception:
                self.progress["value"] = 0

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background="#313131")
    style.configure("TLabel", background="#313131", foreground="#FFFFFF")
    style.configure("Custom.TButton", background="#232323", foreground="#FFFFFF", borderwidth=1, focusthickness=2, focuscolor="#FFFFFF")
    style.map("Custom.TButton",
        background=[('active', '#31363b'), ('pressed', '#181a1b'), ('!active', '#232323')],
        foreground=[('active', '#80cfff'), ('pressed', '#0078d4'), ('!active', '#FFFFFF')],
        relief=[('pressed', 'sunken'), ('!pressed', 'raised')],
        bordercolor=[('active', '#0078d4'), ('!active', '#31363b')],
    )
    style.configure("Terminate.TButton", background="#2d2323", foreground="#ff6b6b", borderwidth=1.5, focusthickness=2, focuscolor="#ff6b6b")
    style.map("Terminate.TButton",
        background=[('active', '#3a2323'), ('pressed', '#181a1b'), ('!active', '#2d2323')],
        foreground=[('active', '#ffbaba'), ('pressed', '#ff6b6b'), ('!active', '#ff6b6b')],
        bordercolor=[('active', '#ff6b6b'), ('!active', '#6b2323')],
        relief=[('pressed', 'sunken'), ('!pressed', 'raised')],
    )
    style.configure(
        "WhiteOnBlack.TCombobox",
        fieldbackground="#232526",
        background="#232526",
        foreground="#e6e6e6",
        selectforeground="#e6e6e6",
        selectbackground="#31363b",
        arrowcolor="#e6e6e6",
        bordercolor="#232526",
        borderwidth=0,
        highlightthickness=0,
        relief="flat",
        padding=6
    )
    style.map(
        "WhiteOnBlack.TCombobox",
        fieldbackground=[('readonly', '#232526')],
        background=[('readonly', '#232526')],
        foreground=[('readonly', '#e6e6e6')],
        selectbackground=[('readonly', '#31363b')],
        selectforeground=[('readonly', '#e6e6e6')],
        arrowcolor=[('readonly', '#e6e6e6')],
    )
    app = MediaDownloader(root)
    root.mainloop()