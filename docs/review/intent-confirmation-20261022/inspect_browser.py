"""Capture the actual rendered design/runtime graph, using Python Playwright."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '.validation/browser-python'))
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8866/graph')
    parser.add_argument('--label', default='design-pending')
    args = parser.parse_args()
    out = Path(__file__).parent / 'browser' / args.label
    out.mkdir(parents=True, exist_ok=False)
    errors, console, requests = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: console.append({'type': message.type, 'text': message.text}))
        page.on('requestfailed', lambda request: requests.append({'url': request.url, 'failure': request.failure}))
        page.goto(args.url, wait_until='domcontentloaded')
        network_idle = True
        try:
            page.wait_for_load_state('networkidle', timeout=5000)
        except Exception:
            # The graph polls its server; verify rendered data instead of assuming silence.
            network_idle = False
        ready_error = None
        try:
            page.wait_for_function('window.graphDebug?.graph?.boxes?.length > 0', timeout=10000)
        except Exception as error:
            ready_error = str(error)
        page.screenshot(path=str(out / 'graph.png'), full_page=True)
        data = {
            'url': args.url,
            'network_idle': network_idle,
            'text': page.locator('body').inner_text(),
            'controls': page.locator('button, select, input').evaluate_all('(els)=>els.map(e=>({tag:e.tagName,id:e.id,text:e.innerText,label:e.getAttribute("aria-label"),type:e.type}))'),
            'graph': page.evaluate('window.graphDebug ? ({metrics:graphDebug.metrics,camera:graphDebug.camera,graph:graphDebug.graph,view:graphDebug.view}) : null'),
            'page_errors': errors,
            'ready_error': ready_error,
            'console': console,
            'failed_requests': requests,
        }
        (out / 'inspection.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({'out': str(out), 'page_errors': errors, 'ready_error': ready_error, 'failed_requests': requests, 'console': console[-6:]}, ensure_ascii=True))
        browser.close()


if __name__ == '__main__':
    main()
