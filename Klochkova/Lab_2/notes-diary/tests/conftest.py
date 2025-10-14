import os
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path

# Определяем путь к папке "Тесты" на рабочем столе
DESKTOP = Path.home() / "Desktop"
SCREENSHOT_DIR = DESKTOP / "Тесты"
SCREENSHOT_DIR.mkdir(exist_ok=True)

@pytest.fixture(scope="module")
def driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Современный headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1280,800")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    yield driver
    driver.quit()

@pytest.fixture(scope="function")
def notes_app(driver):
    # Запускайте локальный сервер: python -m http.server 8000
    driver.get("http://localhost:8000")
    yield driver

    # Скриншот при завершении (опционально)
    test_name = os.environ.get("PYTEST_CURRENT_TEST", "unknown").split("::")[-1].split(" ")[0]
    driver.save_screenshot(SCREENSHOT_DIR / f"{test_name}_final.png")