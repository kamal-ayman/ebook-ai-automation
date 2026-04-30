from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AutomationConfig:
    """Runtime configuration provided by the Tkinter UI."""

    login_url: str
    username: str
    password: str
    quiz_url: str
    gemini_api_key: str
    gemini_model: str = "gemini-3.1-flash-lite-preview"
    headless: bool = False
    close_browser_when_done: bool = False
    max_pages: int = 300
    timeout_seconds: int = 20

    def validate(self) -> None:
        if not self.login_url.strip():
            raise ValueError("Login URL is required.")
        if not self.quiz_url.strip():
            raise ValueError("Quiz URL is required.")
        if not self.username.strip():
            raise ValueError("Username is required.")
        if not self.password:
            raise ValueError("Password is required.")
        if not self.gemini_api_key.strip():
            raise ValueError("Gemini API key is required.")
        if self.max_pages <= 0:
            raise ValueError("Max pages must be greater than 0.")
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be greater than 0.")
