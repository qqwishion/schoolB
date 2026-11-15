"""Local browser acceptance check. Requires a running server and local demo users."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'test-results'
OUT.mkdir(exist_ok=True)
BASE = 'http://127.0.0.1:8000'
credentials = dict(line.split(': ', 1) for line in (ROOT / '.local-accounts.txt').read_text(encoding='utf-8').splitlines() if ': ' in line)
report = {'pages': [], 'browser_errors': [], 'layout': []}

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    page.on('pageerror', lambda exc: report['browser_errors'].append(str(exc)))
    paths = ['/', '/eras/', '/eras/age-18/', '/topics/1/', '/cards/', '/cards/1/', '/quizzes/', '/accounts/login/', '/accounts/register/', '/sources/']
    for path in paths:
        response = page.goto(BASE + path)
        assert response.status == 200, (path, response.status)
        page.locator('body').wait_for()
        broken = page.locator('img').evaluate_all('(images) => images.filter(i => i.complete && i.naturalWidth === 0).map(i=>i.src)')
        assert not broken, broken
        report['pages'].append(path)
    page.goto(BASE)
    page.screenshot(path=str(OUT / 'home-desktop.png'), full_page=True)
    # The keyboard skip link must receive focus and take the reader to main.
    page.keyboard.press('Tab')
    assert page.locator('.skip').evaluate('(el)=>el===document.activeElement')
    page.keyboard.press('Enter')
    assert page.evaluate('location.hash') == '#main'
    page.goto(BASE + '/accounts/login/')
    page.locator('#id_username').fill('student')
    page.locator('#id_password').fill(credentials['student'])
    page.locator('.auth button').click()
    page.wait_for_url('**/profile/')
    page.goto(BASE + '/cards/1/')
    page.locator('summary').click()
    assert page.locator('.prose').is_visible()
    page.locator('.reading-action button').click()
    page.wait_for_url('**/cards/1/')
    assert page.locator('.reading-action button').is_visible()
    # Restore the original reading state after testing the reversible control.
    page.locator('.reading-action button').click()
    page.wait_for_url('**/cards/1/')
    page.goto(BASE + '/quizzes/')
    page.locator('.quiz-tile').first.click()
    page.locator('.start-test button').click()
    page.wait_for_url('**/attempts/*/')
    for question in page.locator('fieldset.question').all(): question.locator('input[type=radio]').first.check()
    page.locator('.test-container form > button').click()
    assert page.locator('.result-banner').is_visible()
    assert page.locator('.review').count() > 0
    result_path = page.url.removeprefix(BASE)
    report['result_url'] = result_path
    page.goto(BASE + '/profile/')
    page.screenshot(path=str(OUT / 'profile-desktop.png'), full_page=True)
    for width in [360, 768, 1440]:
        page.set_viewport_size({'width': width, 'height': 900})
        for path in paths + ['/profile/', result_path]:
            page.goto(BASE + path)
            overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert not overflow, f'Horizontal overflow: {path} at {width}px'
            report['layout'].append({'width': width, 'path': path, 'overflow': overflow})
        page.goto(BASE)
        page.screenshot(path=str(OUT / f'home-{width}.png'), full_page=True)
    page.set_viewport_size({'width': 360, 'height': 800})
    page.goto(BASE)
    page.locator('.menu-button').click()
    assert page.locator('#navigation').is_visible()
    assert page.locator('.menu-button').get_attribute('aria-expanded') == 'true'
    # Staff-only admin and content editing remain usable after the site restyle.
    page.locator('.account button').click()
    page.goto(BASE + '/admin/login/')
    page.locator('#id_username').fill('museum_admin')
    page.locator('#id_password').fill(credentials['museum_admin'])
    page.locator('input[type=submit]').click()
    page.wait_for_url('**/admin/')
    assert page.locator('#site-name').is_visible()
    browser.close()

assert not report['browser_errors'], report['browser_errors']
(OUT / 'browser-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'PASS: {len(report["pages"])} pages, {len(report["layout"])} responsive checks, reading, quiz, login, admin, keyboard and menu. Screenshots: {OUT}')
