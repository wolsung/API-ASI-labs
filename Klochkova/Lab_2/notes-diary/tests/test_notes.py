import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path

DESKTOP = Path.home() / "Desktop"
SCREENSHOT_DIR = DESKTOP / "Тесты"

def take_screenshot(driver, name):
    """Сохраняет скриншот в папку 'Тесты' на рабочем столе"""
    safe_name = "".join(c if c.isalnum() else "_" for c in name)
    path = SCREENSHOT_DIR / f"{safe_name}.png"
    driver.save_screenshot(str(path))
    print(f"📸 Скриншот сохранён: {path}")

def test_create_note(notes_app):
    driver = notes_app
    wait = WebDriverWait(driver, 10)

    # Скриншот начального состояния
    take_screenshot(driver, "01_home_page")

    # Открыть модальное окно
    add_btn = wait.until(EC.element_to_be_clickable((By.ID, "addNoteBtn")))
    add_btn.click()
    take_screenshot(driver, "02_modal_open")

    # Заполнить форму
    wait.until(EC.visibility_of_element_located((By.ID, "noteModal")))
    driver.find_element(By.ID, "noteTitle").send_keys("Тестовая заметка")
    driver.find_element(By.ID, "noteContent").send_keys("Содержание тестовой заметки.")
    driver.find_element(By.ID, "noteTags").send_keys("тест, selenium")
    driver.find_element(By.ID, "notePinned").click()  # Закрепить

    take_screenshot(driver, "03_form_filled")

    # Сохранить
    driver.find_element(By.ID, "saveBtn").click()
    take_screenshot(driver, "04_after_save")

    # Проверить, что заметка появилась
    note_title = wait.until(EC.visibility_of_element_located((By.XPATH, "//h3[text()='Тестовая заметка']")))
    assert note_title.is_displayed()
    assert "pinned" in note_title.find_element(By.XPATH, "..").get_attribute("class")

def test_edit_note(notes_app):
    driver = notes_app
    wait = WebDriverWait(driver, 10)

    # Найти и нажать "Редактировать"
    edit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Редактировать')]")))
    edit_btn.click()
    take_screenshot(driver, "05_edit_modal")

    # Изменить заголовок
    title_input = wait.until(EC.visibility_of_element_located((By.ID, "noteTitle")))
    title_input.clear()
    title_input.send_keys("Обновлённая заметка")
    driver.find_element(By.ID, "saveBtn").click()

    take_screenshot(driver, "06_after_edit")

    # Проверить обновление
    updated = wait.until(EC.visibility_of_element_located((By.XPATH, "//h3[text()='Обновлённая заметка']")))
    assert updated.is_displayed()

def test_filter_by_tag(notes_app):
    driver = notes_app
    wait = WebDriverWait(driver, 10)

    # Ввести тег в фильтр
    tag_filter = driver.find_element(By.ID, "tagFilter")
    tag_filter.clear()
    tag_filter.send_keys("тест")
    take_screenshot(driver, "07_tag_filter_applied")

    # Проверить, что заметка видна
    note = wait.until(EC.visibility_of_element_located((By.XPATH, "//h3[text()='Обновлённая заметка']")))
    assert note.is_displayed()

    # Очистить фильтр
    driver.find_element(By.ID, "clearFilter").click()
    take_screenshot(driver, "08_filter_cleared")

def test_sort_newest(notes_app):
    driver = notes_app
    wait = WebDriverWait(driver, 10)

    # Нажать сортировку "Сначала новые"
    driver.find_element(By.ID, "sortNewest").click()
    take_screenshot(driver, "09_sorted_newest")

    # Проверить, что есть хотя бы одна заметка
    first_note = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".note")))
    assert first_note.is_displayed()

def test_delete_note(notes_app):
    driver = notes_app
    wait = WebDriverWait(driver, 10)

    # Обойти confirm()
    driver.execute_script("window.confirm = function() { return true; }")

    # Нажать "Удалить"
    delete_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Удалить')]")))
    delete_btn.click()
    take_screenshot(driver, "10_after_delete")

    # Проверить, что список пуст или нет заметки
    try:
        WebDriverWait(driver, 5).until(
            EC.invisibility_of_element_located((By.XPATH, "//h3[text()='Обновлённая заметка']"))
        )
    except:
        # Если не исчезла — проверим, что есть "Заметок пока нет"
        empty_state = driver.find_element(By.CLASS_NAME, "empty-state")
        assert empty_state.is_displayed()