from playwright.sync_api import sync_playwright
import urllib.request
import json

try:
    with urllib.request.urlopen("http://localhost:9222/json/list", timeout=2) as resp:
        targets = json.loads(resp.read().decode())
        print(f"CDP Targets count: {len(targets)}")
        for i, t in enumerate(targets):
            print(f"[{i}] type: {t.get('type')}, title: {t.get('title')}, url: {t.get('url')}")
except Exception as e:
    print(f"Could not reach CDP: {e}")
