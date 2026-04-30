from __future__ import annotations

import threading
import tkinter as tk
from queue import Empty, Queue
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

from automation_app.core.config import AutomationConfig
from automation_app.core.models import RunStatus
from automation_app.services.orchestrator import QuizAutomationOrchestrator
from automation_app.utils.logging_utils import stamp


class MainWindow:
    """Tkinter front-end for running quiz automation."""

    def __init__(self) -> None:
        self._root = tk.Tk()
        self._root.title("Quiz Automation App")
        self._root.geometry("920x700")
        self._root.minsize(860, 620)

        self._message_queue: Queue[tuple[str, str]] = Queue()
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._is_running = False

        self.login_url_var = tk.StringVar(value="https://ebook.bu.edu.eg/login/index.php")
        self.quiz_url_var = tk.StringVar(value="https://ebook.bu.edu.eg/mod/quiz/attempt.php?attempt=597320&cmid=44914&page=43")
        self.username_var = tk.StringVar(value="30209060102598")
        self.password_var = tk.StringVar(value="123123123")
        self.api_key_var = tk.StringVar(value="AIzaSyBM2opzmYegsJq_g9EPi6n1AYPhfjeNrJg")
        self.model_var = tk.StringVar(value="gemini-3.1-flash-lite-preview")
        self.max_pages_var = tk.StringVar(value="65")
        self.headless_var = tk.BooleanVar(value=False)
        self.keep_browser_open_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value=RunStatus.IDLE.value)

        self._start_btn: tk.Button
        self._stop_btn: tk.Button
        self._log_box: ScrolledText

        self._build_ui()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.after(120, self._drain_queue)

    def run(self) -> None:
        self._root.mainloop()

    def _build_ui(self) -> None:
        container = tk.Frame(self._root, padx=12, pady=12)
        container.pack(fill="both", expand=True)

        form_frame = tk.LabelFrame(container, text="Automation Input", padx=10, pady=10)
        form_frame.pack(fill="x")

        self._add_labeled_entry(form_frame, 0, "Login URL", self.login_url_var)
        self._add_labeled_entry(form_frame, 1, "Quiz URL", self.quiz_url_var)
        self._add_labeled_entry(form_frame, 2, "Username", self.username_var)
        self._add_labeled_entry(form_frame, 3, "Password", self.password_var, show="*")
        self._add_labeled_entry(form_frame, 4, "Gemini API Key", self.api_key_var, show="*")
        self._add_labeled_entry(form_frame, 5, "Gemini Model", self.model_var)
        self._add_labeled_entry(form_frame, 6, "Max Pages", self.max_pages_var, width=14)

        options_frame = tk.Frame(container)
        options_frame.pack(fill="x", pady=(10, 0))

        tk.Checkbutton(options_frame, text="Run Chrome in headless mode", variable=self.headless_var).pack(
            side="left", padx=(0, 16)
        )
        tk.Checkbutton(
            options_frame,
            text="Keep browser open when done",
            variable=self.keep_browser_open_var,
        ).pack(side="left")

        action_frame = tk.Frame(container)
        action_frame.pack(fill="x", pady=(10, 0))

        self._start_btn = tk.Button(action_frame, text="Start Automation", command=self._start_automation)
        self._start_btn.pack(side="left")

        self._stop_btn = tk.Button(action_frame, text="Stop", command=self._stop_automation, state="disabled")
        self._stop_btn.pack(side="left", padx=(8, 0))

        status_frame = tk.Frame(container)
        status_frame.pack(fill="x", pady=(10, 0))
        tk.Label(status_frame, text="Status:").pack(side="left")
        tk.Label(status_frame, textvariable=self.status_var, fg="#004a99").pack(side="left", padx=(6, 0))

        log_frame = tk.LabelFrame(container, text="Runtime Logs", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))

        self._log_box = ScrolledText(log_frame, wrap="word", height=20, state="disabled")
        self._log_box.pack(fill="both", expand=True)

    def _add_labeled_entry(
        self,
        parent: tk.Widget,
        row: int,
        label_text: str,
        variable: tk.StringVar,
        show: str | None = None,
        width: int = 80,
    ) -> None:
        label = tk.Label(parent, text=label_text, anchor="w")
        label.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)

        entry = tk.Entry(parent, textvariable=variable, width=width, show=show)
        entry.grid(row=row, column=1, sticky="ew", pady=4)

        parent.grid_columnconfigure(1, weight=1)

    def _start_automation(self) -> None:
        if self._is_running:
            return

        try:
            max_pages = int(self.max_pages_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Max pages must be a valid integer.")
            return

        config = AutomationConfig(
            login_url=self.login_url_var.get().strip(),
            quiz_url=self.quiz_url_var.get().strip(),
            username=self.username_var.get().strip(),
            password=self.password_var.get(),
            gemini_api_key=self.api_key_var.get().strip(),
            gemini_model=self.model_var.get().strip() or "gemini-3.1-flash-lite-preview",
            max_pages=max_pages,
            headless=self.headless_var.get(),
            close_browser_when_done=not self.keep_browser_open_var.get(),
        )

        try:
            config.validate()
        except ValueError as exc:
            messagebox.showerror("Missing or invalid input", str(exc))
            return

        self._is_running = True
        self._stop_event = threading.Event()
        self._set_ui_running(True)
        self._set_status(RunStatus.RUNNING)
        self._append_log(stamp("Automation started."))

        self._worker_thread = threading.Thread(
            target=self._run_automation_worker,
            args=(config,),
            daemon=True,
        )
        self._worker_thread.start()

    def _stop_automation(self) -> None:
        if not self._is_running:
            return

        self._stop_event.set()
        self._append_log(stamp("Stop requested by user."))

    def _run_automation_worker(self, config: AutomationConfig) -> None:
        orchestrator = QuizAutomationOrchestrator(log=self._enqueue_worker_log)
        status = orchestrator.run(config, self._stop_event)

        self._message_queue.put(("status", status.value))
        self._message_queue.put(("done", ""))

    def _enqueue_worker_log(self, message: str) -> None:
        self._message_queue.put(("log", stamp(message)))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._message_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "done":
                    self._is_running = False
                    self._set_ui_running(False)
        except Empty:
            pass
        finally:
            self._root.after(120, self._drain_queue)

    def _set_status(self, status: RunStatus) -> None:
        self.status_var.set(status.value)

    def _set_ui_running(self, running: bool) -> None:
        self._start_btn.configure(state="disabled" if running else "normal")
        self._stop_btn.configure(state="normal" if running else "disabled")

    def _append_log(self, line: str) -> None:
        self._log_box.configure(state="normal")
        self._log_box.insert("end", line + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _on_close(self) -> None:
        if self._is_running:
            should_close = messagebox.askyesno(
                "Automation is running",
                "Automation is still running. Stop and close the app?",
            )
            if not should_close:
                return
            self._stop_event.set()

        self._root.destroy()
