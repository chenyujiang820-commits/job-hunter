from pathlib import Path

from playwright.sync_api import sync_playwright


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" and "server responded" not in message.text else None)
    page.goto("http://127.0.0.1:5173")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="runtime/ui-smoke-desktop.png", full_page=True)
    assert page.get_by_text("把职位判断").is_visible()
    assert page.get_by_role("button", name="登录工作台").is_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="runtime/ui-smoke-mobile.png", full_page=True)
    assert page.get_by_text("把职位判断").is_visible()
    assert not errors, errors
    browser.close()
