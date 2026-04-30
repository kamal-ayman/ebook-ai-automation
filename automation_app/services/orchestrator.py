from __future__ import annotations

import threading
from typing import Callable

from automation_app.core.config import AutomationConfig
from automation_app.core.models import RunStatus
from automation_app.services.auth_service import AuthService
from automation_app.services.browser_service import BrowserService
from automation_app.services.moodle_quiz_service import MoodleQuizService


class QuizAutomationOrchestrator:
    """Coordinates login, question solving, and quiz navigation."""

    def __init__(self, log: Callable[[str], None]) -> None:
        self._log = log

    def run(self, config: AutomationConfig, stop_event: threading.Event) -> RunStatus:
        try:
            config.validate()
        except ValueError as exc:
            self._log(f"Configuration error: {exc}")
            return RunStatus.FAILED

        browser_service = BrowserService(config, self._log)
        driver = None
        wait = None

        try:
            driver, wait = browser_service.start()

            auth_service = AuthService(driver, wait, self._log)
            quiz_service = MoodleQuizService(driver, wait, self._log)
            try:
                from automation_app.services.gemini_solver import GeminiAnswerSolver
            except ModuleNotFoundError as exc:
                self._log("Gemini dependency is missing. Install requirements and retry.")
                self._log(f"Dependency error: {exc}")
                return RunStatus.FAILED
            solver = GeminiAnswerSolver(config.gemini_api_key, config.gemini_model, self._log)

            auth_service.login(config)
            if stop_event.is_set():
                return RunStatus.STOPPED

            self._log("Opening quiz link...")
            driver.get(config.quiz_url)

            page_count = 0
            while not stop_event.is_set():
                quiz_service.wait_for_page_ready()

                questions = quiz_service.extract_questions_with_retry(retries=1)
                if questions:
                    self._log(f"Detected {len(questions)} question(s) on current page.")
                else:
                    self._log("No solvable questions found on current page.")

                for question in questions:
                    if stop_event.is_set():
                        break

                    selected_index = solver.choose_option(question)
                    quiz_service.select_answer(question, selected_index)

                    label = question.question_number or question.question_id or "?"
                    self._log(f"Answered question {label} with option {selected_index + 1}.")

                if stop_event.is_set():
                    break

                if quiz_service.click_next_page():
                    page_count += 1
                    if page_count >= config.max_pages:
                        self._log("Reached max pages limit. Stopping to prevent infinite loop.")
                        return RunStatus.STOPPED
                    continue

                if quiz_service.click_first_unanswered_question():
                    continue

                # Only move to summary after attempting to solve all questions on this page.
                if quiz_service.click_finish_attempt_link():
                    continue

                if quiz_service.click_submit_all_and_finish():
                    self._log("Final submit triggered.")
                    return RunStatus.COMPLETED

                self._log("No next or finish control found. Ending automation loop.")
                return RunStatus.COMPLETED

            return RunStatus.STOPPED
        except Exception as exc:  # noqa: BLE001
            self._log(f"Automation failed: {exc}")
            return RunStatus.FAILED
        finally:
            if driver is not None:
                if config.close_browser_when_done:
                    browser_service.stop()
                else:
                    self._log("Browser kept open by configuration.")
