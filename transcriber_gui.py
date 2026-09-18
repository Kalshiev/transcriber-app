#!/usr/bin/env python3
"""
Transcriber App — graphical interface (Windows-friendly).

A simple tkinter GUI on top of the Whisper transcription logic in
``transcriber.py``. tkinter ships with Python on Windows, so no extra
packages are needed beyond those already required by the CLI tool.
"""

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from transcriber import check_if_audio, transcribe_audio

# Language choices: (code, label)
LANGUAGES = [
    ("auto", "Auto-detect"),
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("pt", "Portuguese"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("zh", "Chinese"),
    ("ru", "Russian"),
    ("nl", "Dutch"),
    ("ko", "Korean"),
]

MODELS = ["tiny", "base", "small", "medium", "large"]

# Messages posted from the worker thread to the UI thread.
_STATUS = "status"          # update the status label
_FINISHED = "finished"      # transcription completed successfully
_ERROR = "error"            # transcription failed


class TranscriberApp:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.worker = None

        root.title("Transcriber App")
        root.geometry("760x640")
        root.minsize(620, 520)

        self._build_ui()

        # Poll the worker queue so UI updates happen on the main thread.
        self.root.after(100, self._process_queue)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # File selection
        file_frame = ttk.LabelFrame(self.root, text="File", padding=10)
        file_frame.pack(fill="x", padx=10, pady=(10, 0))

        self.file_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_var)
        file_entry.pack(side="left", fill="x", expand=True)

        browse_btn = ttk.Button(
            file_frame, text="Browse…", command=self._browse_file
        )
        browse_btn.pack(side="left", padx=(8, 0))

        # Options
        opts_frame = ttk.LabelFrame(self.root, text="Options", padding=10)
        opts_frame.pack(fill="x", padx=10, pady=10)

        opts_frame.columnconfigure(1, weight=1)

        ttk.Label(opts_frame, text="Language:").grid(
            row=0, column=0, sticky="w", **pad
        )
        self.language_var = tk.StringVar(value="es")
        language_combo = ttk.Combobox(
            opts_frame,
            textvariable=self.language_var,
            values=[label for _, label in LANGUAGES],
            state="readonly",
        )
        language_combo.grid(row=0, column=1, sticky="ew", **pad)
        # Map displayed label -> language code at transcription time.

        ttk.Label(opts_frame, text="Model:").grid(
            row=1, column=0, sticky="w", **pad
        )
        self.model_var = tk.StringVar(value="medium")
        model_combo = ttk.Combobox(
            opts_frame,
            textvariable=self.model_var,
            values=MODELS,
            state="readonly",
        )
        model_combo.grid(row=1, column=1, sticky="ew", **pad)

        # Action button + progress
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill="x", padx=10)

        self.transcribe_btn = ttk.Button(
            action_frame, text="Transcribe", command=self._start_transcription
        )
        self.transcribe_btn.pack(side="left")

        self.progress = ttk.Progressbar(
            action_frame, mode="indeterminate", length=200
        )
        self.progress.pack(side="left", padx=10, fill="x", expand=True)

        self.status_var = tk.StringVar(value="Ready. Choose an audio/video file.")
        status_label = ttk.Label(
            self.root, textvariable=self.status_var, anchor="w", padding=(10, 4)
        )
        status_label.pack(fill="x")

        # Output
        output_frame = ttk.LabelFrame(self.root, text="Transcription", padding=6)
        output_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.text = tk.Text(output_frame, wrap="word", height=12)
        self.text.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.text.yview
        )
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scroll.set)

        self.save_btn = ttk.Button(
            self.root, text="Save As…", command=self._save_as, state="disabled"
        )
        self.save_btn.pack(anchor="e", padx=10, pady=(0, 10))

    # -------------------------------------------------------------- helpers
    def _language_code(self):
        """Convert the displayed language label back to a Whisper code."""
        label = self.language_var.get()
        for code, name in LANGUAGES:
            if name == label:
                return code
        return "auto"

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select an audio or video file",
            filetypes=[
                (
                    "Audio / Video files",
                    "*.mp3 *.m4a *.wav *.ogg *.flac *.aac *.wma *.opus "
                    "*.mp4 *.mov *.mkv *.avi *.webm *.m4b",
                ),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.file_var.set(path)

    def _save_as(self):
        text = self.text.get("1.0", "end-1c").strip()
        if not text:
            return
        path = filedialog.asksaveasfilename(
            title="Save transcription",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self._set_status(f"Saved to '{path}'")
        except OSError as e:
            messagebox.showerror("Save failed", str(e))

    def _set_status(self, message):
        self.status_var.set(message)

    # ------------------------------------------------------- transcription
    def _start_transcription(self):
        if self.worker and self.worker.is_alive():
            return

        file_path = self.file_var.get().strip()
        if not file_path:
            messagebox.showwarning(
                "Missing file", "Please choose an audio or video file first."
            )
            return

        try:
            check_if_audio(file_path)
        except (TypeError, FileNotFoundError) as e:
            messagebox.showerror("Invalid file", str(e))
            return

        language = self._language_code()
        model = self.model_var.get()

        self._set_busy(True)
        self.text.delete("1.0", "end")
        self._set_status("Starting…")

        self.worker = threading.Thread(
            target=self._transcribe_worker,
            args=(file_path, language, model),
            daemon=True,
        )
        self.worker.start()

    def _transcribe_worker(self, file_path, language, model):
        try:
            text = transcribe_audio(
                file_path,
                language,
                model,
                on_status=lambda msg: self.queue.put((_STATUS, msg)),
            )
            self.queue.put((_FINISHED, text))
        except Exception as e:  # noqa: BLE001 — surface any error to the user
            self.queue.put((_ERROR, str(e)))

    def _process_queue(self):
        try:
            while True:
                message = self.queue.get_nowait()
                kind, payload = message

                if kind == _STATUS:
                    self._set_status(payload)
                elif kind == _FINISHED:
                    self._set_busy(False)
                    self.text.delete("1.0", "end")
                    self.text.insert("1.0", payload)
                    self.save_btn.configure(state="normal")
                    self._set_status("Done.")
                elif kind == _ERROR:
                    self._set_busy(False)
                    self._set_status("Failed.")
                    messagebox.showerror("Transcription error", payload)
        except queue.Empty:
            pass

        self.root.after(100, self._process_queue)

    def _set_busy(self, busy):
        if busy:
            self.transcribe_btn.configure(state="disabled")
            self.save_btn.configure(state="disabled")
            self.progress.start(12)
        else:
            self.transcribe_btn.configure(state="normal")
            self.progress.stop()


def main():
    root = tk.Tk()
    TranscriberApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
