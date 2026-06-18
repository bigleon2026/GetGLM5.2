"""一次性：打开 Chrome，手动登录 bigmodel.cn，保存登录态"""
import time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

AUTH_FILE = Path(__file__).parent / "auth_state.json"

print("=" * 50)
print("  登录态设置（一次性）")
print("=" * 50)
print("即将打开 Chrome → 请手动登录 bigmodel.cn")
print()

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.goto("https://bigmodel.cn/glm-coding", wait_until="domcontentloaded")
    
    print("请在 Chrome 窗口中完成登录...")
    input("\n登录成功后按 Enter 保存...")
    
    context.storage_state(path=str(AUTH_FILE))
    data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    names = [c["name"] for c in data["cookies"]]
    print(f"\n✅ 已保存 {len(data['cookies'])} cookies")
    key = [n for n in names if any(k in n.lower() for k in ["token","auth","login"])]
    print(f"   关键: {key}")
    
    context.close()
    browser.close()

print("\n完成！现在可以运行抢购: python glm_sniper.py --now")
