from __future__ import annotations

import json
import re
import time
from typing import Callable, Optional

import google.generativeai as genai

from automation_app.core.models import QuizQuestion


class GeminiAnswerSolver:
    """Uses Gemini models to select the most likely correct option."""

    _MAX_RATE_LIMIT_RETRIES = 5
    _DEFAULT_RATE_LIMIT_DELAY_SECONDS = 30.0

    def __init__(self, api_key: str, model: str, log: Callable[[str], None]) -> None:
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name=model)
        self._log = log

    def choose_option(self, question: QuizQuestion) -> int:
        if not question.options:
            raise ValueError("Question has no options.")
        if len(question.options) == 1:
            return 0

        prompt = self._build_prompt(question)
        raw = self._request_choice(prompt)

        index = self._extract_index(raw)
        if index is None:
            self._log("Gemini response did not contain a valid index. Falling back to option 1.")
            return 0

        return self._normalize_index(index, len(question.options))

    def _request_choice(self, prompt: str) -> str:
        system_message = (
            "You are a quiz-solving assistant. "
            "Return strict JSON only: {\"selected_index\": <int>, \"reason\": \"short text\"}. "
            "selected_index must be zero-based."
        )
        full_prompt = f"{system_message}\n\n{prompt}"

        attempt = 0
        while True:
            try:
                response = self._generate_content(full_prompt)
                return self._response_to_text(response)
            except Exception as exc:  # noqa: BLE001
                retry_delay_seconds = self._extract_retry_delay_seconds(exc)
                if retry_delay_seconds is None:
                    raise

                attempt += 1
                if attempt > self._MAX_RATE_LIMIT_RETRIES:
                    self._log(
                        "Gemini rate limit persisted after retries. Falling back to option 1 for this question."
                    )
                    return ""

                self._log(
                    f"Gemini quota/rate limit hit. Waiting {retry_delay_seconds:.1f}s before retry "
                    f"({attempt}/{self._MAX_RATE_LIMIT_RETRIES})."
                )
                time.sleep(retry_delay_seconds)

    def _generate_content(self, full_prompt: str) -> object:
        try:
            return self._model.generate_content(
                full_prompt,
                generation_config={"temperature": 0, "response_mime_type": "application/json"},
            )
        except TypeError:
            return self._model.generate_content(
                full_prompt,
                generation_config={"temperature": 0},
            )

    def _extract_retry_delay_seconds(self, exc: Exception) -> Optional[float]:
        text = str(exc)
        normalized = text.lower()

        is_rate_limited = any(
            marker in normalized
            for marker in ("429", "quota", "rate limit", "retry_delay", "resource_exhausted")
        )
        if not is_rate_limited:
            return None

        retry_in_match = re.search(r"please\s+retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s", text, flags=re.IGNORECASE)
        if retry_in_match:
            return max(1.0, float(retry_in_match.group(1)))

        seconds_match = re.search(r"retry_delay\s*\{[^}]*seconds:\s*(\d+)", text, flags=re.IGNORECASE)
        nanos_match = re.search(r"retry_delay\s*\{[^}]*nanos:\s*(\d+)", text, flags=re.IGNORECASE)
        if seconds_match:
            seconds = float(seconds_match.group(1))
            nanos = float(nanos_match.group(1)) / 1_000_000_000 if nanos_match else 0.0
            return max(1.0, seconds + nanos)

        return self._DEFAULT_RATE_LIMIT_DELAY_SECONDS

    def _response_to_text(self, response: object) -> str:
        try:
            text = getattr(response, "text", "")
            if text:
                return text
        except Exception:  # noqa: BLE001
            pass

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue

            parts = getattr(content, "parts", None) or []
            chunks: list[str] = []
            for part in parts:
                part_text = getattr(part, "text", "")
                if part_text:
                    chunks.append(part_text)

            if chunks:
                return "\n".join(chunks)

        return ""

    def _build_prompt(self, question: QuizQuestion) -> str:
        options_text = "\n".join(
            f"{option.index}. {option.text}" for option in question.options
        )

        return (
            "Choose the best answer for this multiple-choice question.\n"
            f"Question: {question.text}\n"
            "Options:\n"
            f"{options_text}\n"
            "Return JSON only."
        )

    def _extract_index(self, raw: str) -> Optional[int]:
        raw = raw.strip()
        if not raw:
            return None

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for key in ("selected_index", "selected_option_index", "index", "answer_index"):
                    if key in parsed:
                        return int(parsed[key])
        except (ValueError, TypeError, json.JSONDecodeError):
            pass

        match = re.search(r"-?\d+", raw)
        if match:
            return int(match.group(0))

        return None

    def _normalize_index(self, index: int, option_count: int) -> int:
        if 0 <= index < option_count:
            return index

        # Tolerate 1-based responses from the model.
        if 1 <= index <= option_count:
            return index - 1

        return max(0, min(option_count - 1, index))