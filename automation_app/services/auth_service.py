from __future__ import annotations

from typing import Callable, List, Optional

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from automation_app.core.config import AutomationConfig


class AuthService:
    """Handles login actions on the Moodle login page."""

    USERNAME_SELECTORS: List[str] = [
        "#username",
        "input[name='username']",
        "input[type='text'][autocomplete='username']",
    ]

    PASSWORD_SELECTORS: List[str] = [
        "#password",
        "input[name='password']",
        "input[type='password'][autocomplete='current-password']",
    ]

    LOGIN_BUTTON_SELECTORS: List[str] = [
        "#loginbtn",
        "button[type='submit']",
        "input[type='submit']",
    ]

    def __init__(
        self,
        driver: WebDriver,
        wait: WebDriverWait,
        log: Callable[[str], None],
    ) -> None:
        self._driver = driver
        self._wait = wait
        self._log = log

    def login(self, config: AutomationConfig) -> None:
        self._log("Opening login page...")
        self._driver.get(config.login_url)

        username = self._find_first_element(self.USERNAME_SELECTORS)
        password = self._find_first_element(self.PASSWORD_SELECTORS)

        if username is None or password is None:
            self._log("Login form not detected. Continuing without login action.")
            return

        self._log("Filling username and password...")
        username.clear()
        username.send_keys(config.username)

        password.clear()
        password.send_keys(config.password)

        login_button = self._find_first_element(self.LOGIN_BUTTON_SELECTORS)
        if login_button is not None:
            self._log("Clicking login button...")
            login_button.click()
        else:
            self._log("Login button not found, submitting password field...")
            password.submit()

        self._wait_for_login_transition()

    def _wait_for_login_transition(self) -> None:
        try:
            self._wait.until_not(ec.presence_of_element_located((By.CSS_SELECTOR, "#username")))
            self._log("Login form is gone. Continuing automation...")
        except TimeoutException:
            self._log("Login transition timed out. Continuing anyway...")

    def _find_first_element(self, selectors: List[str]):
        for selector in selectors:
            elements = self._driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if element.is_displayed():
                    return element
        return None
