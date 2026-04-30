from __future__ import annotations

import re
from typing import Callable, List, Optional, Sequence

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from automation_app.core.exceptions import QuizParsingError
from automation_app.core.models import QuestionOption, QuizQuestion


class MoodleQuizService:
    """Parses Moodle quiz pages and performs navigation/answer actions."""

    def __init__(
        self,
        driver: WebDriver,
        wait: WebDriverWait,
        log: Callable[[str], None],
    ) -> None:
        self._driver = driver
        self._wait = wait
        self._log = log

    def wait_for_page_ready(self) -> None:
        self._wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    def extract_questions(self) -> List[QuizQuestion]:
        questions: List[QuizQuestion] = []
        question_blocks = self._driver.find_elements(By.CSS_SELECTOR, "div.que")

        for block in question_blocks:
            try:
                question_id = (block.get_attribute("id") or "").strip()
                question_number = self._first_text(block, [".qno"]) or ""
                question_text = self._normalize_text(self._first_text(block, [".qtext"]) or "")

                option_inputs = block.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                options: List[QuestionOption] = []
                seen_keys = set()

                for input_element in option_inputs:
                    value = (input_element.get_attribute("value") or "").strip()
                    if value == "-1":
                        continue

                    input_id = (input_element.get_attribute("id") or "").strip()
                    if not input_id and not value:
                        continue

                    key = input_id or f"value:{value}"
                    if key in seen_keys:
                        continue

                    text = self._normalize_text(self._resolve_option_text(block, input_element))
                    if not text:
                        continue

                    options.append(
                        QuestionOption(
                            index=len(options),
                            text=text,
                            input_id=input_id,
                            value=value,
                        )
                    )
                    seen_keys.add(key)

                if question_text and options:
                    questions.append(
                        QuizQuestion(
                            question_id=question_id,
                            question_number=question_number,
                            text=question_text,
                            options=options,
                        )
                    )
            except StaleElementReferenceException:
                continue

        return questions

    def extract_questions_with_retry(self, retries: int = 1) -> List[QuizQuestion]:
        questions = self.extract_questions()
        if questions:
            return questions

        for _ in range(max(0, retries)):
            try:
                WebDriverWait(self._driver, 2).until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, "div.que")) > 0
                )
            except TimeoutException:
                pass

            questions = self.extract_questions()
            if questions:
                return questions

        return questions

    def select_answer(self, question: QuizQuestion, selected_index: int) -> None:
        if not question.options:
            raise QuizParsingError(f"Question has no options: {question.question_id}")

        if selected_index < 0 or selected_index >= len(question.options):
            raise QuizParsingError(
                f"Selected option index {selected_index} is out of range for question {question.question_id}."
            )

        option = question.options[selected_index]

        target: Optional[WebElement] = None
        if option.input_id:
            try:
                target = self._driver.find_element(By.ID, option.input_id)
            except NoSuchElementException:
                target = None

        if target is None:
            target = self._driver.find_element(
                By.XPATH,
                (
                    f"//*[@id={self._xpath_literal(question.question_id)}]"
                    f"//input[@type='radio' and @value={self._xpath_literal(option.value)}]"
                ),
            )

        if not target.is_selected():
            self._safe_click(target)

    def click_next_page(self) -> bool:
        element = self._find_first_clickable(
            css_selectors=[
                "#mod_quiz-next-nav",
                "input[name='next']",
                "button[name='next']",
                "input.mod_quiz-next-nav",
                "button.mod_quiz-next-nav",
                "input[type='submit'][value*='Next']",
                "input[type='submit'][value*='NEXT']",
                "input[type='submit'][value*='التالي']",
            ],
            xpaths=[
                "//button[contains(translate(normalize-space(.), 'NEXT', 'next'), 'next')]",
                "//input[@type='submit' and contains(translate(@value, 'NEXT', 'next'), 'next')]",
            ],
        )
        if element is None:
            return False

        self._log("Clicking Next page...")
        self._safe_click(element)
        return True

    def click_finish_attempt_link(self) -> bool:
        element = self._find_first_clickable(
            css_selectors=[
                "a.endtestlink",
                "a[href*='/mod/quiz/summary.php']",
            ],
            xpaths=[
                "//a[contains(translate(normalize-space(.), 'FINISH ATTEMPT', 'finish attempt'), 'finish attempt')]",
                "//a[contains(translate(normalize-space(.), 'FINISH', 'finish'), 'finish')]",
            ],
        )
        if element is None:
            return False

        self._log("Clicking Finish attempt link...")
        self._safe_click(element)
        return True

    def click_first_unanswered_question(self) -> bool:
        element = self._find_first_clickable(
            css_selectors=[
                "#quiznavblock .qnbutton.notyetanswered",
                ".qnbutton.notyetanswered",
            ],
        )
        if element is None:
            return False

        self._log("Navigating to first unanswered question...")
        self._safe_click(element)
        return True

    def click_submit_all_and_finish(self) -> bool:
        primary = self._find_first_clickable(
            css_selectors=[
                "input[name='finishattempt']",
                "button[name='finishattempt']",
                "#id_submitbutton",
                "input[type='submit'][value*='Submit all and finish']",
                "input[type='submit'][value*='Finish attempt']",
            ],
            xpaths=[
                "//button[contains(normalize-space(.), 'Submit all and finish')]",
                "//input[@type='submit' and contains(@value, 'Submit all and finish')]",
                "//button[contains(normalize-space(.), 'Finish attempt')]",
                "//input[@type='submit' and contains(@value, 'Finish attempt')]",
                "//button[contains(normalize-space(.), 'إنهاء')]",
                "//input[@type='submit' and contains(@value, 'إنهاء')]",
            ],
        )

        if primary is None:
            return False

        self._log("Clicking final submit action...")
        self._safe_click(primary)

        # Some Moodle themes show a confirmation button after the first click.
        try:
            WebDriverWait(self._driver, 2).until(lambda _d: self._confirm_button_exists())
            confirm = self._find_first_clickable(
                css_selectors=[
                    "#id_submitbutton",
                    "button.btn-primary",
                ],
                xpaths=[
                    "//button[contains(normalize-space(.), 'Submit all and finish')]",
                    "//input[@type='submit' and contains(@value, 'Submit all and finish')]",
                ],
            )
            if confirm is not None:
                self._log("Clicking confirmation submit button...")
                self._safe_click(confirm)
        except TimeoutException:
            pass

        return True

    def _confirm_button_exists(self) -> bool:
        return bool(
            self._driver.find_elements(By.CSS_SELECTOR, "#id_submitbutton")
            or self._driver.find_elements(By.XPATH, "//button[contains(., 'Submit all and finish')]")
        )

    def _find_first_clickable(
        self,
        css_selectors: Sequence[str] = (),
        xpaths: Sequence[str] = (),
    ) -> Optional[WebElement]:
        for selector in css_selectors:
            for element in self._driver.find_elements(By.CSS_SELECTOR, selector):
                if self._is_clickable(element):
                    return element

        for xpath in xpaths:
            for element in self._driver.find_elements(By.XPATH, xpath):
                if self._is_clickable(element):
                    return element

        return None

    def _is_clickable(self, element: WebElement) -> bool:
        try:
            return element.is_displayed() and element.is_enabled()
        except StaleElementReferenceException:
            return False

    def _safe_click(self, element: WebElement) -> None:
        self._driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        try:
            element.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            self._driver.execute_script("arguments[0].click();", element)

    def _resolve_option_text(self, question_block: WebElement, input_element: WebElement) -> str:
        aria_labelledby = (input_element.get_attribute("aria-labelledby") or "").strip()
        if aria_labelledby:
            chunks: List[str] = []
            for element_id in aria_labelledby.split():
                targets = question_block.find_elements(By.ID, element_id)
                if not targets:
                    targets = self._driver.find_elements(By.ID, element_id)
                for target in targets:
                    text = target.text.strip()
                    if text:
                        chunks.append(text)
            if chunks:
                return " ".join(chunks)

        sibling = input_element.find_elements(By.XPATH, "./following-sibling::*[1]")
        if sibling:
            text = sibling[0].text.strip()
            if text:
                return text

        row = input_element.find_elements(
            By.XPATH,
            "./ancestor::div[contains(@class,'r0') or contains(@class,'r1')][1]",
        )
        if row:
            return row[0].text.strip()

        return ""

    def _first_text(self, root: WebElement, selectors: Sequence[str]) -> Optional[str]:
        for selector in selectors:
            elements = root.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = element.text.strip()
                if text:
                    return text
        return None

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _xpath_literal(self, value: str) -> str:
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'

        parts = value.split("'")
        quoted_parts = [f"'{part}'" for part in parts]
        return "concat(" + ", \"'\", ".join(quoted_parts) + ")"
