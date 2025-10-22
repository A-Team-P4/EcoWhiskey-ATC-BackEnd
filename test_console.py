#!/usr/bin/env python3
"""
Tkinter-based UI for exercising the EcoWhiskey ATC API.

Features:
    * Register users via /users/.
    * Login and store bearer tokens for authenticated requests.
    * Upload existing audio files, or record audio within the UI and send it to /audio/analyze.
    * Open and stream the audio URL returned by the API (e.g., S3 readback objects).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
import wave
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

try:
    import requests
    from requests import Response, Session
    from requests.exceptions import RequestException
except ImportError as exc:  # pragma: no cover - helper script
    raise SystemExit(
        "The 'requests' package is required. Install it with `pip install requests`."
    ) from exc

try:
    import sounddevice as sd
except ImportError as exc:  # pragma: no cover - helper script
    raise SystemExit(
        "The 'sounddevice' package is required for recording/playback.\n"
        "Install it with `pip install sounddevice` and ensure PortAudio is available."
    ) from exc

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
RECORD_SAMPLE_RATE = 16_000
RECORD_CHANNELS = 1


@dataclass
class SessionState:
    base_url: str = DEFAULT_BASE_URL.rstrip("/")
    token: Optional[str] = os.getenv("API_BEARER_TOKEN")

    def auth_headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}


class ApiTester(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("EcoWhiskey ATC Test Console")
        self.minsize(920, 700)

        self.state = SessionState()
        self.session: Session = requests.Session()

        self.last_audio_url: Optional[str] = None

        # Recording state
        self.is_recording = False
        self._record_stream: Optional[sd.InputStream] = None
        self._recording_chunks: list[np.ndarray] = []
        self._recording_data: Optional[np.ndarray] = None
        self._recording_temp_file: Optional[Path] = None
        self._temp_files: set[Path] = set()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)
        self.log(f"UI ready. Using API base URL: {self.state.base_url}")
        if self.state.token:
            self.log("Bearer token loaded from environment.")

    # --- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        config_frame = ttk.LabelFrame(self, text="Configuration")
        config_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        config_frame.columnconfigure(1, weight=1)

        ttk.Label(config_frame, text="Base URL").grid(row=0, column=0, padx=6, pady=6)
        self.base_url_var = tk.StringVar(value=self.state.base_url)
        ttk.Entry(config_frame, textvariable=self.base_url_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 6), pady=6
        )
        ttk.Button(
            config_frame,
            text="Apply",
            command=self._update_base_url,
            width=10,
        ).grid(row=0, column=2, padx=6, pady=6)

        ttk.Label(config_frame, text="Bearer Token").grid(
            row=1, column=0, padx=6, pady=6
        )
        self.token_var = tk.StringVar(value=self.state.token or "")
        self.token_entry = ttk.Entry(
            config_frame,
            textvariable=self.token_var,
            show="•",
        )
        self.token_entry.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=6)
        ttk.Button(
            config_frame,
            text="Set",
            command=lambda: self._set_token(self.token_var.get().strip() or None),
            width=10,
        ).grid(row=1, column=2, padx=6, pady=6, sticky="w")
        ttk.Button(
            config_frame,
            text="Reveal",
            command=self._toggle_token_visibility,
            width=10,
        ).grid(row=1, column=3, padx=(0, 6), pady=6, sticky="w")
        ttk.Button(
            config_frame,
            text="Clear",
            command=lambda: self._set_token(None),
            width=10,
        ).grid(row=1, column=4, padx=6, pady=6, sticky="w")

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

        self._build_register_tab()
        self._build_login_tab()
        self._build_audio_tab()

        console_frame = ttk.LabelFrame(self, text="Console Output")
        console_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(6, 12))
        console_frame.rowconfigure(0, weight=1)
        console_frame.columnconfigure(0, weight=1)

        self.output = ScrolledText(console_frame, wrap="word", height=12, state="disabled")
        self.output.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

    def _build_register_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        frame.columnconfigure(1, weight=1)
        self.notebook.add(frame, text="Register User")

        ttk.Label(frame, text="Email").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.reg_email = tk.StringVar()
        ttk.Entry(frame, textvariable=self.reg_email).grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=6
        )

        ttk.Label(frame, text="First name").grid(
            row=1, column=0, padx=8, pady=6, sticky="w"
        )
        self.reg_first = tk.StringVar()
        ttk.Entry(frame, textvariable=self.reg_first).grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=6
        )

        ttk.Label(frame, text="Last name").grid(
            row=2, column=0, padx=8, pady=6, sticky="w"
        )
        self.reg_last = tk.StringVar()
        ttk.Entry(frame, textvariable=self.reg_last).grid(
            row=2, column=1, sticky="ew", padx=(0, 8), pady=6
        )

        ttk.Label(frame, text="Password").grid(
            row=3, column=0, padx=8, pady=6, sticky="w"
        )
        self.reg_password = tk.StringVar()
        ttk.Entry(
            frame,
            textvariable=self.reg_password,
            show="•",
        ).grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=6)

        ttk.Label(frame, text="Account type").grid(
            row=4, column=0, padx=8, pady=6, sticky="w"
        )
        self.account_type_var = tk.StringVar(value="student")
        account_type = ttk.Combobox(
            frame,
            textvariable=self.account_type_var,
            values=("student", "instructor"),
            state="readonly",
        )
        account_type.grid(row=4, column=1, sticky="ew", padx=(0, 8), pady=6)
        self.account_type_var.trace_add("write", self._handle_account_type_change)

        ttk.Label(frame, text="School (required for instructors)").grid(
            row=5, column=0, padx=8, pady=6, sticky="w"
        )
        self.reg_school = tk.StringVar()
        self.school_entry = ttk.Entry(frame, textvariable=self.reg_school, state="disabled")
        self.school_entry.grid(row=5, column=1, sticky="ew", padx=(0, 8), pady=6)

        ttk.Button(
            frame,
            text="Register",
            command=self._on_register,
            width=18,
        ).grid(row=6, column=1, padx=8, pady=(12, 6), sticky="e")

    def _build_login_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        frame.columnconfigure(1, weight=1)
        self.notebook.add(frame, text="Login")

        ttk.Label(frame, text="Email").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.login_email = tk.StringVar()
        ttk.Entry(frame, textvariable=self.login_email).grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=6
        )

        ttk.Label(frame, text="Password").grid(
            row=1, column=0, padx=8, pady=6, sticky="w"
        )
        self.login_password = tk.StringVar()
        ttk.Entry(
            frame,
            textvariable=self.login_password,
            show="•",
        ).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=6)

        ttk.Button(
            frame,
            text="Login",
            command=self._on_login,
            width=18,
        ).grid(row=2, column=1, padx=8, pady=(12, 6), sticky="e")

    def _build_audio_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        frame.columnconfigure(1, weight=1)
        self.notebook.add(frame, text="Audio Analyze")

        ttk.Label(frame, text="Session ID").grid(
            row=0, column=0, padx=8, pady=6, sticky="w"
        )
        self.audio_session_id = tk.StringVar(value=str(uuid.uuid4()))
        ttk.Entry(frame, textvariable=self.audio_session_id).grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=6
        )
        ttk.Button(
            frame,
            text="New UUID",
            command=lambda: self.audio_session_id.set(str(uuid.uuid4())),
            width=12,
        ).grid(row=0, column=2, padx=6, pady=6)

        ttk.Label(frame, text="Frequency").grid(
            row=1, column=0, padx=8, pady=6, sticky="w"
        )
        self.audio_frequency = tk.StringVar(value="118.0")
        ttk.Entry(frame, textvariable=self.audio_frequency).grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=6
        )

        ttk.Label(frame, text="Audio file (MP3/M4A/WAV)").grid(
            row=2, column=0, padx=8, pady=6, sticky="w"
        )
        self.audio_path = tk.StringVar()
        ttk.Entry(frame, textvariable=self.audio_path).grid(
            row=2, column=1, sticky="ew", padx=(0, 8), pady=6
        )
        ttk.Button(
            frame,
            text="Browse",
            command=self._choose_audio_file,
            width=12,
        ).grid(row=2, column=2, padx=6, pady=6)

        ttk.Button(
            frame,
            text="Call /audio/analyze",
            command=self._on_audio_analyze,
            width=22,
        ).grid(row=3, column=1, padx=8, pady=(12, 6), sticky="e")

        ttk.Separator(frame).grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=12)

        record_frame = ttk.LabelFrame(frame, text="Record Audio")
        record_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=6, pady=(0, 12))
        record_frame.columnconfigure(1, weight=1)

        self.record_button = ttk.Button(
            record_frame,
            text="Start Recording",
            command=self._toggle_recording,
            width=18,
        )
        self.record_button.grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self.play_recording_button = ttk.Button(
            record_frame,
            text="Play Recording",
            command=self._play_recorded_audio,
            state="disabled",
            width=18,
        )
        self.play_recording_button.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        self.use_recording_button = ttk.Button(
            record_frame,
            text="Use Recording For Upload",
            command=self._use_recording_for_upload,
            state="disabled",
            width=24,
        )
        self.use_recording_button.grid(row=0, column=2, padx=8, pady=8, sticky="w")

        self.record_status_var = tk.StringVar(value="Idle")
        ttk.Label(record_frame, textvariable=self.record_status_var).grid(
            row=1, column=0, columnspan=3, padx=8, pady=(0, 8), sticky="w"
        )

        ttk.Separator(frame).grid(row=6, column=0, columnspan=3, sticky="ew", padx=6, pady=12)

        playback_frame = ttk.LabelFrame(frame, text="Last Analyze Response")
        playback_frame.grid(row=7, column=0, columnspan=3, sticky="nsew", padx=6, pady=(0, 12))
        playback_frame.columnconfigure(0, weight=1)

        self.open_audio_url_button = ttk.Button(
            playback_frame,
            text="Open Audio URL",
            command=self._open_last_audio_url,
            state="disabled",
            width=20,
        )
        self.open_audio_url_button.grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self.play_audio_url_button = ttk.Button(
            playback_frame,
            text="Play Audio Stream",
            command=self._play_last_audio,
            state="disabled",
            width=20,
        )
        self.play_audio_url_button.grid(row=0, column=1, padx=8, pady=8, sticky="w")

    # --- Event handlers --------------------------------------------------

    def _update_base_url(self) -> None:
        new_url = self.base_url_var.get().strip().rstrip("/")
        if not new_url:
            messagebox.showerror("Invalid URL", "Base URL cannot be empty.")
            return
        self.state.base_url = new_url
        self.log(f"Base URL set to {new_url}")

    def _set_token(self, token: Optional[str]) -> None:
        self.state.token = token
        self.token_var.set(token or "")
        self.token_entry.configure(show="•")
        self.log("Bearer token cleared." if not token else "Bearer token updated.")

    def _toggle_token_visibility(self) -> None:
        current = self.token_entry.cget("show")
        self.token_entry.configure(show="" if current else "•")

    def _handle_account_type_change(self, *_args: Any) -> None:
        account_type = (self.account_type_var.get() or "").lower()
        if account_type == "instructor":
            self.school_entry.configure(state="normal")
        else:
            self.school_entry.configure(state="disabled")
            self.reg_school.set("")

    def _choose_audio_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=(
                ("Audio files", "*.mp3 *.m4a *.mp4 *.wav"),
                ("All files", "*.*"),
            ),
        )
        if path:
            self.audio_path.set(path)

    def _on_register(self) -> None:
        payload = {
            "email": self.reg_email.get().strip(),
            "firstName": self.reg_first.get().strip(),
            "lastName": self.reg_last.get().strip(),
            "password": self.reg_password.get(),
            "accountType": (self.account_type_var.get() or "").lower(),
        }

        if not payload["email"]:
            messagebox.showerror("Validation", "Email is required.")
            return
        if not payload["firstName"] or not payload["lastName"]:
            messagebox.showerror("Validation", "First and last name are required.")
            return
        if not payload["password"]:
            messagebox.showerror("Validation", "Password is required.")
            return

        if payload["accountType"] == "instructor":
            school = self.reg_school.get().strip()
            if not school:
                messagebox.showerror("Validation", "School is required for instructors.")
                return
            payload["school"] = school
        elif payload["accountType"] == "student":
            payload.pop("school", None)
        else:
            messagebox.showerror(
                "Validation", "Account type must be 'student' or 'instructor'."
            )
            return

        self._run_async(
            lambda: self._perform_request(
                "Register user",
                "POST",
                "/users/",
                include_auth=False,
                json=payload,
            )
        )

    def _on_login(self) -> None:
        payload = {
            "email": self.login_email.get().strip(),
            "password": self.login_password.get(),
        }

        if not payload["email"] or not payload["password"]:
            messagebox.showerror("Validation", "Email and password are required.")
            return

        def task() -> None:
            resp = self._perform_request(
                "Login",
                "POST",
                "/auth/login",
                include_auth=False,
                json=payload,
            )
            if not resp:
                return
            try:
                data = resp.json()
            except ValueError:
                self.log("Login succeeded but response was not JSON.")
                return

            token = data.get("accessToken") or data.get("access_token")
            if not token:
                self.log("Login response did not include a bearer token.")
                return

            self.after(0, lambda: self._set_token(token))

        self._run_async(task)

    def _on_audio_analyze(self) -> None:
        session_id = self.audio_session_id.get().strip()
        frequency = self.audio_frequency.get().strip()
        audio_path = Path(self.audio_path.get().strip())

        if not session_id:
            messagebox.showerror("Validation", "Session ID is required.")
            return
        if not frequency:
            messagebox.showerror("Validation", "Frequency is required.")
            return
        if not audio_path.is_file():
            messagebox.showerror("Validation", "Audio file path is invalid.")
            return

        def task() -> None:
            prepared = self._prepare_audio_for_upload(audio_path)
            if prepared is None:
                return
            prepared_path, mime_type, cleanup_path = prepared
            try:
                with prepared_path.open("rb") as handle:
                    files = {
                        "audio_file": (prepared_path.name, handle, mime_type),
                    }
                    data = {"session_id": session_id, "frequency": frequency}
                    self._perform_request(
                        "Audio analyze",
                        "POST",
                        "/audio/analyze",
                        data=data,
                        files=files,
                    )
            except OSError as exc:
                self.log(f"Error opening audio file: {exc}")
            finally:
                if cleanup_path:
                    try:
                        cleanup_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    self._temp_files.discard(cleanup_path)

        self._run_async(task)

    # --- Recording -------------------------------------------------------

    def _toggle_recording(self) -> None:
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        try:
            if self._recording_temp_file and self._recording_temp_file.exists():
                self._recording_temp_file.unlink(missing_ok=True)
                self._temp_files.discard(self._recording_temp_file)
        except OSError:
            pass

        self._recording_chunks = []
        self._recording_data = None

        try:
            self._record_stream = sd.InputStream(
                samplerate=RECORD_SAMPLE_RATE,
                channels=RECORD_CHANNELS,
                callback=self._record_callback,
            )
            self._record_stream.start()
        except Exception as exc:  # noqa: BLE001 - surface audio device errors
            self.log(f"Unable to start recording: {exc}")
            messagebox.showerror("Recording error", str(exc))
            self._record_stream = None
            return

        self.is_recording = True
        self.record_button.config(text="Stop Recording")
        self.play_recording_button.config(state="disabled")
        self.use_recording_button.config(state="disabled")
        self.record_status_var.set("Recording…")
        self.log("Recording started (16 kHz mono).")

    def _record_callback(self, indata: np.ndarray, _frames: int, _time, status) -> None:
        if status:
            self.log(f"Recording status: {status}")  # pragma: no cover - passthrough
        self._recording_chunks.append(indata.copy())

    def _stop_recording(self) -> None:
        if not self.is_recording:
            return

        self.is_recording = False
        self.record_button.config(text="Start Recording")

        if self._record_stream:
            try:
                self._record_stream.stop()
                self._record_stream.close()
            except Exception:
                pass
            finally:
                self._record_stream = None

        if not self._recording_chunks:
            self.record_status_var.set("No audio captured.")
            self.log("Recording stopped but no audio was captured.")
            return

        data = np.concatenate(self._recording_chunks, axis=0)
        self._recording_data = data

        scaled = np.int16(np.clip(data, -1.0, 1.0) * 32767)
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                with wave.open(tmp, "wb") as wf:
                    wf.setnchannels(RECORD_CHANNELS)
                    wf.setsampwidth(2)
                    wf.setframerate(RECORD_SAMPLE_RATE)
                    wf.writeframes(scaled.tobytes())
                self._recording_temp_file = Path(tmp.name)
                self._temp_files.add(self._recording_temp_file)
        except OSError as exc:
            self.log(f"Failed to persist recording: {exc}")
            self.record_status_var.set("Recording saved failed.")
            return

        duration = data.shape[0] / RECORD_SAMPLE_RATE
        self.record_status_var.set(f"Recorded {duration:.1f}s to {self._recording_temp_file.name}")
        self.log(
            f"Recording saved to {self._recording_temp_file} "
            f"({duration:.1f}s at {RECORD_SAMPLE_RATE} Hz)."
        )
        self.play_recording_button.config(state="normal")
        self.use_recording_button.config(state="normal")

    def _play_recorded_audio(self) -> None:
        if self._recording_data is None:
            messagebox.showinfo("Playback", "No recording available yet.")
            return

        def task() -> None:
            self.log("Playing recorded audio…")
            try:
                sd.play(self._recording_data, samplerate=RECORD_SAMPLE_RATE)
                sd.wait()
            except Exception as exc:  # noqa: BLE001
                self.log(f"Playback failed: {exc}")

        self._run_async(task)

    def _use_recording_for_upload(self) -> None:
        if not self._recording_temp_file:
            messagebox.showinfo("Recording", "No recording available to upload.")
            return
        self.audio_path.set(str(self._recording_temp_file))
        self.log(f"Recording selected for upload: {self._recording_temp_file}")

    # --- Analyze response audio -----------------------------------------

    def _set_last_audio_url(self, url: Optional[str]) -> None:
        self.last_audio_url = url
        state = "normal" if url else "disabled"
        self.open_audio_url_button.config(state=state)
        self.play_audio_url_button.config(state=state)
        if url:
            self.log(f"Captured audio URL: {url}")

    def _open_last_audio_url(self) -> None:
        if not self.last_audio_url:
            messagebox.showinfo("Audio URL", "No audio URL available yet.")
            return
        self.log(f"Opening audio URL in browser: {self.last_audio_url}")
        webbrowser.open(self.last_audio_url, new=2, autoraise=True)

    def _play_last_audio(self) -> None:
        if not self.last_audio_url:
            messagebox.showinfo("Audio URL", "No audio URL available yet.")
            return

        def task() -> None:
            self.log(f"Downloading audio from {self.last_audio_url}")
            try:
                resp = self.session.get(self.last_audio_url, timeout=60)
                resp.raise_for_status()
            except RequestException as exc:
                self.log(f"Failed to fetch audio: {exc}")
                return

            try:
                self._play_wav_bytes(resp.content)
                self.log("Audio playback finished.")
            except Exception as exc:  # noqa: BLE001
                self.log(f"Unable to play remote audio: {exc}")

        self._run_async(task)

    def _play_wav_bytes(self, payload: bytes) -> None:
        with wave.open(io.BytesIO(payload)) as wf:
            sample_width = wf.getsampwidth()
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

        if sample_width not in (2, 4):
            raise ValueError("Only 16-bit or 32-bit PCM WAV files are supported.")

        dtype = np.int16 if sample_width == 2 else np.int32
        audio = np.frombuffer(frames, dtype=dtype)
        if channels > 1:
            audio = audio.reshape(-1, channels)

        max_int = float(2 ** (sample_width * 8 - 1))
        float_audio = audio.astype(np.float32) / max_int

        sd.play(float_audio, samplerate=sample_rate)
        sd.wait()

    # --- Networking helpers ----------------------------------------------

    def _run_async(self, callback: Any) -> None:
        thread = threading.Thread(target=callback, daemon=True)
        thread.start()

    def _perform_request(
        self,
        label: str,
        method: str,
        endpoint: str,
        *,
        include_auth: bool = True,
        **kwargs: Any,
    ) -> Optional[Response]:
        url = endpoint
        if not endpoint.startswith(("http://", "https://")):
            url = f"{self.state.base_url}{endpoint}"

        headers = kwargs.pop("headers", {}) or {}
        if include_auth:
            headers.update(self.state.auth_headers())

        self.log(f"{label}: {method.upper()} {url}")
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=headers if headers else None,
                timeout=60,
                **kwargs,
            )
        except RequestException as exc:
            self.log(f"{label} failed: {exc}")
            return None

        self._log_response(label, response)
        if response.status_code >= 400:
            return None
        return response

    # --- Logging helpers -------------------------------------------------

    def log(self, message: str) -> None:
        def _append() -> None:
            self.output.configure(state="normal")
            self.output.insert("end", f"{message}\n")
            self.output.configure(state="disabled")
            self.output.see("end")

        self.after(0, _append)

    def _log_response(self, label: str, response: Response) -> None:
        audio_url: Optional[str] = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                audio_url = (
                    payload.get("audio_url")
                    or payload.get("audioUrl")
                    or payload.get("audio-url")
                )
            body = json.dumps(payload, indent=2)
        except ValueError:
            payload = None
            body = response.text.strip() or "<empty body>"

        message = (
            f"{label} response ({response.status_code}):\n"
            f"Headers: {dict(response.headers)}\n"
            f"{body}\n"
        )
        self.log(message)

        if audio_url:
            self.after(0, lambda url=audio_url: self._set_last_audio_url(url))

    # ---------------------------------------------------------------------

    def _prepare_audio_for_upload(
        self,
        original_path: Path,
    ) -> Optional[tuple[Path, str, Optional[Path]]]:
        ext = original_path.suffix.lower()
        allowed = {
            ".mp3": "audio/mpeg",
            ".mpeg": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".mp4": "audio/mp4",
        }
        if ext in allowed:
            return original_path, allowed[ext], None

        if ext == ".wav":
            converted = self._convert_with_ffmpeg(original_path, ".mp3")
            if converted:
                self.log(f"Converted WAV to MP3 for upload: {converted.name}")
                return converted, "audio/mpeg", converted
            return None

        messagebox.showerror(
            "Unsupported audio format",
            "Please choose an MP3 or M4A file. WAV inputs can be converted automatically "
            "if ffmpeg is installed.",
        )
        return None

    def _convert_with_ffmpeg(self, source: Path, target_suffix: str) -> Optional[Path]:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.log("ffmpeg not found. Unable to convert audio automatically.")
            messagebox.showerror(
                "Conversion error",
                "ffmpeg is required to convert WAV recordings to MP3.\n"
                "Install ffmpeg or provide an MP3/M4A file manually.",
            )
            return None

        fd, tmp_path = tempfile.mkstemp(suffix=target_suffix)
        os.close(fd)
        target = Path(tmp_path)

        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            str(target),
        ]

        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            self.log(f"ffmpeg invocation failed: {exc}")
            target.unlink(missing_ok=True)
            messagebox.showerror("Conversion error", f"ffmpeg failed to run: {exc}")
            return None

        if result.returncode != 0:
            self.log(f"ffmpeg conversion failed: {result.stderr.strip()}")
            target.unlink(missing_ok=True)
            messagebox.showerror(
                "Conversion error",
                "ffmpeg could not convert the audio file. See console output for details.",
            )
            return None

        self._temp_files.add(target)
        return target

    def _on_app_close(self) -> None:
        if self.is_recording:
            self._stop_recording()
        for path in list(self._temp_files):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self._temp_files.clear()
        self.destroy()


def main() -> None:
    app = ApiTester()
    app.mainloop()


if __name__ == "__main__":
    main()
