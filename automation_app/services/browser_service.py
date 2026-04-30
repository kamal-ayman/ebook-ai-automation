from __future__ import annotations

from typing import Callable, Optional, Tuple

from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait

from automation_app.core.config import AutomationConfig


class BrowserService:
    """Owns Selenium WebDriver lifecycle."""

    def __init__(self, config: AutomationConfig, log: Callable[[str], None]) -> None:
        self._config = config
        self._log = log
        self._driver: Optional[Chrome] = None
        self._wait: Optional[WebDriverWait] = None

    def start(self) -> Tuple[Chrome, WebDriverWait]:
        options = ChromeOptions()
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1366,900")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")

        if self._config.headless:
            options.add_argument("--headless=new")

        if not self._config.close_browser_when_done:
            options.add_experimental_option("detach", True)

        self._log("Launching Chrome browser...")
        self._driver = Chrome(options=options)
        self._driver.set_page_load_timeout(max(self._config.timeout_seconds, 30))

        self._wait = WebDriverWait(self._driver, self._config.timeout_seconds)
        return self._driver, self._wait

    def stop(self) -> None:
        if self._driver is None:
            return

        self._log("Closing Chrome browser...")
        self._driver.quit()
        self._driver = None
        self._wait = None
