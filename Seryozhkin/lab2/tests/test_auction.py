import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# === НАСТРОЙКИ ===
# путь к твоему локальному index.html
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HTML_PATH = f"file:///{os.path.join(PROJECT_PATH, 'index.html')}"

def setup_driver():
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1200, 800)
    return driver


def test_add_artwork():
    driver = setup_driver()
    driver.get(HTML_PATH)
    time.sleep(1)

    # --- Добавление картины ---
    title_input = driver.find_element(By.ID, "title")
    author_input = driver.find_element(By.ID, "author")
    price_input = driver.find_element(By.ID, "price")
    add_button = driver.find_element(By.CSS_SELECTOR, "form button")

    title_input.send_keys("Звёздная ночь")
    author_input.send_keys("Винсент Ван Гог")
    price_input.send_keys("1000")
    add_button.click()

    time.sleep(0.5)

    # Проверка, что картина появилась
    art_items = driver.find_elements(By.CLASS_NAME, "art-item")
    assert len(art_items) > 0, "Картина не добавилась!"
    assert "Звёздная ночь" in art_items[0].text

    driver.quit()


def test_make_bid():
    driver = setup_driver()
    driver.get(HTML_PATH)
    time.sleep(1)

    # Проверим, есть ли хотя бы одна картина (если нет — добавим)
    if not driver.find_elements(By.CLASS_NAME, "art-item"):
        driver.find_element(By.ID, "title").send_keys("Мона Лиза")
        driver.find_element(By.ID, "author").send_keys("Леонардо да Винчи")
        driver.find_element(By.ID, "price").send_keys("2000")
        driver.find_element(By.CSS_SELECTOR, "form button").click()
        time.sleep(0.5)

    # Получаем текущую цену
    price_el = driver.find_element(By.CSS_SELECTOR, ".art-item span[id^='price-']")
    old_price = int(price_el.text)

    # Делаем ставку
    bid_button = driver.find_element(By.CLASS_NAME, "bid-btn")
    bid_button.click()
    time.sleep(0.5)

    # Проверяем, что цена увеличилась
    new_price = int(driver.find_element(By.CSS_SELECTOR, ".art-item span[id^='price-']").text)
    assert new_price > old_price, "Ставка не сработала!"

    driver.quit()


def test_end_auction():
    driver = setup_driver()
    driver.get(HTML_PATH)
    time.sleep(1)

    # Добавим хотя бы одну картину, если нет
    if not driver.find_elements(By.CLASS_NAME, "art-item"):
        driver.find_element(By.ID, "title").send_keys("Последний день Помпеи")
        driver.find_element(By.ID, "author").send_keys("Брюллов")
        driver.find_element(By.ID, "price").send_keys("1500")
        driver.find_element(By.CSS_SELECTOR, "form button").click()
        time.sleep(0.5)

    # Завершить торги
    end_button = driver.find_element(By.ID, "end-auction")
    end_button.click()
    time.sleep(0.5)

    # Проверить, что появилось сообщение о победителе
    winner_text = driver.find_element(By.ID, "winner").text
    assert "Победила" in winner_text or "Победил" in winner_text, "Не найдено сообщение о победителе"

    driver.quit()
