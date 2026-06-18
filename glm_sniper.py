"""
GLM Coding Plan 抢购脚本 v5
方案：auth_state.json 保存登录态 + Playwright 自动化
"""
import os, sys, json, time, argparse
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

SD = Path(__file__).parent
SCREENSHOT_DIR = SD / "screenshots"
AUTH_FILE = SD / "auth_state.json"
TARGET_URL = "https://bigmodel.cn/glm-coding"


def ss(page, name):
    try:
        p = SCREENSHOT_DIR / f"{datetime.now().strftime('%H%M%S')}_{name}.png"
        page.screenshot(path=str(p), full_page=True)
        print(f"  [screenshot: {p.name}]")
    except: pass


def main_flow(target_time=None, cycle="monthly"):
    # Check auth
    if not AUTH_FILE.exists():
        print("❌ auth_state.json 不存在！请先运行: python setup_auth.py")
        return

    # Timing
    if target_time:
        target_dt = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        if target_dt > now:
            w = (target_dt - now).total_seconds()
            print(f"[timer] target={target_time} wait={w:.0f}s")
            if w > 10:
                time.sleep(w - 10)
            print("[timer] pre-launching...")

    SCREENSHOT_DIR.mkdir(exist_ok=True)

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=str(AUTH_FILE),
        )
        page = context.new_page()
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # Check login
        has_login = page.evaluate("""() => {
            let f = false;
            document.querySelectorAll('button').forEach(b => {
                if (b.innerText?.trim() === '登录 / 注册') f = true;
            });
            return f;
        }""")
        if has_login:
            print("❌ 未登录！请重新运行: python setup_auth.py")
            ss(page, "not_logged_in")
            return
        print("[OK] 已登录")

        # Precise wait
        if target_time:
            target_dt = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
            r = (target_dt - datetime.now()).total_seconds()
            if r > 0.3:
                print(f"[timer] precise wait {r:.1f}s...")
                time.sleep(r - 0.1)
                while datetime.now() < target_dt: pass

        # === Polling wait for button to become active ===
        # The button shows "暂时售罄" until stock is available
        # Poll aggressively to catch the moment it flips to "特惠订阅"
        print("=" * 50)
        print("  POLLING: waiting for button...")
        print("=" * 50)
        
        poll_start = time.time()
        poll_count = 0
        while True:
            poll_count += 1
            
            # Check Pro button state
            state = page.evaluate("""() => {
                const cards = document.querySelectorAll('.package-card-box');
                for (const c of cards) {
                    if (c.innerText.includes('Pro')) {
                        const btn = c.querySelector('.buy-btn');
                        if (!btn) return {found: false};
                        return {
                            text: btn.innerText?.trim(),
                            disabled: btn.disabled,
                            class: btn.className,
                        };
                    }
                }
                return {found: false};
            }""")
            
            btn_text = state.get("text", "")
            elapsed = time.time() - poll_start
            
            if poll_count % 10 == 1 or "售罄" not in btn_text:
                print(f"  [poll {poll_count} | {elapsed:.0f}s] btn='{btn_text}' disabled={state.get('disabled')}")
            
            # Button is ready!
            if not state.get("disabled") and "售罄" not in btn_text and "订阅" in btn_text:
                print(f"  >>> BUTTON ACTIVE after {elapsed:.0f}s! <<<")
                break
            
            # Timeout after 30 minutes
            if elapsed > 1800:
                print("  [timeout] 30 min no stock")
                ss(page, "timeout")
                return
            
            # Refresh page every 5 seconds to get latest state
            if poll_count > 1 and poll_count % 5 == 0:
                page.reload(wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(1500)
                # Re-select billing cycle after refresh
                cmap = {"monthly": "连续包月", "quarterly": "连续包季", "yearly": "连续包年"}
                target_tab = cmap.get(cycle, "连续包月")
                page.evaluate("""(t) => {
                    document.querySelectorAll('.switch-tab-item').forEach(i => {
                        if (i.querySelector('span')?.innerText?.trim() === t) i.click();
                    });
                }""", target_tab)
                page.wait_for_timeout(500)
            else:
                time.sleep(1)

        # Click Pro
        print("[click] Pro subscribe")
        r = page.evaluate("""() => {
            const cards = document.querySelectorAll('.package-card-box');
            for (const c of cards) {
                if (c.innerText.includes('Pro')) {
                    const btn = c.querySelector('.buy-btn');
                    if (btn && !btn.disabled) { btn.click(); return {ok: true}; }
                    return {ok: false, r: btn ? 'disabled' : 'not found'};
                }
            }
            return {ok: false, r: 'card not found'};
        }""")
        print(f"  {'OK' if r.get('ok') else 'FAIL: ' + str(r)}")
        if not r.get('ok'):
            ss(page, "click_failed")
            return

        # Handle dialogs
        for attempt in range(5):
            page.wait_for_timeout(800)
            st = page.evaluate("""() => {
                const r = {};
                document.querySelectorAll('button').forEach(b => {
                    const t = b.innerText?.trim();
                    if (t === '已知悉，继续订阅') r.cont = true;
                    if (t === '前往认证') r.auth = true;
                    if (t === '确认支付' || t === '支付') r.pay = true;
                });
                const cb = document.querySelector('input[type="checkbox"]');
                r.cbChecked = cb?.checked || false;
                return r;
            }""")
            print(f"  [dialog {attempt}] cont={st.get('cont')} auth={st.get('auth')} pay={st.get('pay')}")

            if st.get('auth'):
                page.evaluate("""() => {
                    const btn = document.querySelector('[class*="real-name-auth"] .el-dialog__headerbtn');
                    if (btn) btn.click();
                }""")
                page.wait_for_timeout(500)
                continue

            if st.get('cont'):
                if not st.get('cbChecked'):
                    page.evaluate("""() => {
                        const cb = document.querySelector('input[type="checkbox"]');
                        if (cb && !cb.checked) cb.click();
                    }""")
                    page.wait_for_timeout(300)
                page.evaluate("""() => {
                    document.querySelectorAll('button').forEach(b => {
                        if (b.innerText?.trim() === '已知悉，继续订阅') b.click();
                    });
                }""")
                page.wait_for_timeout(1500)
                continue

            if st.get('pay'):
                print("\n*** DONE - payment page reached! ***")
                ss(page, "payment")
                break

            if not st.get('cont') and not st.get('auth') and not st.get('pay'):
                print("  [info] no dialog, checking...")
                break

        print("\n[browser stays open 60s]")
        time.sleep(60)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        pw.stop()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--time", "-t", type=str)
    p.add_argument("--now", "-n", action="store_true")
    p.add_argument("--cycle", type=str, default="monthly",
                   choices=["monthly", "quarterly", "yearly"])
    args = p.parse_args()

    target = args.time
    cycle = args.cycle
    if not target and not args.now:
        cfg = SD / "sniper_config.json"
        if cfg.exists():
            c = json.loads(open(cfg, encoding="utf-8").read())
            target = c.get("target_time")
            cycle = c.get("billing_cycle", cycle)
            print(f"[config] target={target}")

    if not target and not args.now:
        p.print_help()
        sys.exit(1)

    main_flow(target_time=target if target else None, cycle=cycle)
