"""
GLM Coding Plan 抢购脚本 v3
目标：个人套餐 → Pro → 连续包月 → 抢购

用法：
  python glm_sniper.py --time "2026-06-19 09:00:00"
  python glm_sniper.py --now       （测试模式，不实际支付）

前提：
  1. Chrome 已登录 bigmodel.cn 且完成实名认证
  2. 运行前关闭所有 Chrome 窗口（脚本会用你的 profile 启动）
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent
SCREENSHOT_DIR = SCRIPT_DIR / "screenshots"
CHROME_USER_DATA = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
TARGET_URL = "https://bigmodel.cn/glm-coding"
BILLING_CYCLE = "monthly"  # monthly / quarterly / yearly
HEADLESS = False  # 建议可见模式，方便确认状态


def ss(page, name: str):
    """截图"""
    try:
        p = SCREENSHOT_DIR / f"{datetime.now().strftime('%H%M%S')}_{name}.png"
        page.screenshot(path=str(p), full_page=True)
        print(f"  📸 {p.name}")
    except Exception:
        pass


def find_and_click(page, text: str, tag: str = "button") -> bool:
    """在 evaluate 内查找并点击含指定文字的按钮（vanilla JS）"""
    return page.evaluate("""([text, tag]) => {
        const els = document.querySelectorAll(tag);
        for (const el of els) {
            if (el.innerText?.trim() === text) {
                el.click();
                return true;
            }
        }
        return false;
    }""", [text, tag])


def switch_billing_cycle(page, cycle: str):
    """切换计费周期：monthly/quarterly/yearly"""
    mapping = {"monthly": "连续包月", "quarterly": "连续包季", "yearly": "连续包年"}
    target = mapping.get(cycle, "连续包月")
    print(f"🔄 切换到: {target}")

    page.evaluate("""(target) => {
        const items = document.querySelectorAll('.switch-tab-item');
        for (const item of items) {
            const span = item.querySelector('span');
            if (span && span.innerText.trim() === target) {
                item.click();
                return;
            }
        }
    }""", target)
    page.wait_for_timeout(600)

    # 验证
    active = page.evaluate("""() => {
        const items = document.querySelectorAll('.switch-tab-item');
        for (const item of items) {
            if (item.classList.contains('active')) {
                return item.querySelector('span')?.innerText?.trim();
            }
        }
        return '?';
    }""")
    print(f"  ✅ 当前: {active}")


def click_pro_subscribe(page) -> bool:
    """点击 Pro 卡片的特惠订阅按钮"""
    print("🎯 点击 Pro 特惠订阅...")
    result = page.evaluate("""() => {
        const cards = document.querySelectorAll('.package-card-box');
        for (const card of cards) {
            if (card.innerText.includes('Pro')) {
                const btn = card.querySelector('.buy-btn');
                if (btn && !btn.disabled) {
                    btn.click();
                    return {success: true, text: btn.innerText.trim()};
                }
                return {success: false, reason: btn ? 'disabled' : 'not found'};
            }
        }
        return {success: false, reason: 'Pro card not found'};
    }""")
    ok = result.get("success")
    print(f"  {'✅' if ok else '❌'} {result}")
    return ok


def close_auth_dialog(page) -> bool:
    """关闭实名认证弹窗"""
    closed = page.evaluate("""() => {
        // Method 1: header close button
        const closeBtn = document.querySelector('[class*="real-name-auth"] .el-dialog__headerbtn');
        if (closeBtn) { closeBtn.click(); return 'headerbtn'; }
        // Method 2: dialog close button (X icon in el-dialog)
        const wrapper = document.querySelector('.el-dialog__wrapper');
        if (wrapper) {
            const headerbtn = wrapper.querySelector('.el-dialog__headerbtn');
            if (headerbtn) { headerbtn.click(); return 'dialog-headerbtn'; }
        }
        return 'none';
    }""")
    if closed != 'none':
        print(f"  ✅ 关闭实名认证弹窗 ({closed})")
        page.wait_for_timeout(500)
        return True
    return False


def handle_flow(page) -> dict:
    """
    处理购买流程弹窗。
    返回: {'status': 'payment'|'login_required'|'unknown', ...}
    """
    page.wait_for_timeout(800)

    # 扫描当前按钮
    state = page.evaluate("""() => {
        const result = {};
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            const t = btn.innerText?.trim();
            if (t === '已知悉，继续订阅') result.continueBtn = true;
            if (t === '暂不订阅') result.cancelBtn = true;
            if (t === '前往认证') result.authBtn = true;
            if (t === '登录') result.loginBtn = true;
            if (t === '确认支付' || t === '支付') result.payBtn = true;
        }
        const cb = document.querySelector('input[type="checkbox"]');
        result.agreement = !!cb;
        result.agreementChecked = cb?.checked || false;

        // Check for visible login dialog
        const dialogs = document.querySelectorAll('.el-dialog__wrapper');
        for (const d of dialogs) {
            if (d.style.display !== 'none' && d.offsetParent !== null) {
                const text = d.innerText.substring(0, 200);
                if (text.includes('登录') && text.includes('手机号')) result.loginDialog = true;
                if (text.includes('实名认证')) result.authDialog = true;
            }
        }
        return result;
    }""")

    print(f"  状态: {json.dumps(state, ensure_ascii=False)}")

    # 优先级处理
    if state.get("loginDialog"):
        return {"status": "login_required", "msg": "需要登录，cookies 可能已过期"}

    if state.get("authDialog") or state.get("authBtn"):
        close_auth_dialog(page)
        page.wait_for_timeout(500)
        # 重新扫描
        return handle_flow(page)

    if state.get("continueBtn"):
        print("  📋 订阅确认弹窗")
        # 勾选协议
        if state.get("agreement") and not state.get("agreementChecked"):
            page.evaluate("""() => {
                const cb = document.querySelector('input[type="checkbox"]');
                if (cb && !cb.checked) cb.click();
            }""")
            page.wait_for_timeout(300)
        # 点击继续
        find_and_click(page, "已知悉，继续订阅")
        page.wait_for_timeout(1500)
        # 递归检查下一页
        return handle_flow(page)

    if state.get("payBtn"):
        return {"status": "payment", "msg": "到达支付页面"}

    # 检查是否跳转到了其他页面（支付成功之类）
    url = page.url
    if "pay" in url.lower() or "order" in url.lower() or "success" in url.lower():
        return {"status": "payment", "msg": f"跳转到: {url}"}

    if state.get("cancelBtn") and not state.get("continueBtn"):
        return {"status": "stuck", "msg": "仅有取消按钮，可能已到达目标页"}

    return {"status": "unknown", "state": state}


def main_flow(sniper_mode: bool = False, target_time: str = None, billing_cycle: str = "monthly"):
    """主流程"""

    # === 定时逻辑 ===
    if target_time:
        target_dt = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        if target_dt > now:
            wait = (target_dt - now).total_seconds()
            print(f"⏰ 目标: {target_time} | 等待 {wait:.0f}s")
            if wait > 15:
                time.sleep(wait - 15)
            # 预加载阶段
            print("\n🔄 提前 15s 启动浏览器...")
        else:
            print(f"⚠️ 时间已过，立即执行")

    # === 启动浏览器 ===
    print("🌐 启动 Chrome（使用你的 profile）...")
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    # 直接用 Chrome profile（Chrome 已关闭，无锁冲突）
    pw = sync_playwright().start()
    context = None
    page = None

    try:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_USER_DATA),
            headless=HEADLESS,
            channel="chrome",
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        # === 加载页面 ===
        print(f"📄 加载: {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # 检查登录态
        has_login_btn = page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                if (btn.innerText?.trim() === '登录 / 注册') return true;
            }
            return false;
        }""")
        if has_login_btn:
            print("❌ 未登录！请先用 Chrome 登录 bigmodel.cn 后关闭 Chrome 重试")
            ss(page, "not_logged_in")
            return

        print("✅ 已登录")

        # === 等到精确时间 ===
        if target_time:
            target_dt = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
            remaining = (target_dt - datetime.now()).total_seconds()
            if remaining > 0.3:
                print(f"⏳ 精确等待 {remaining:.1f}s...")
                time.sleep(remaining - 0.1)
                # 忙等最后 0.1s
                while datetime.now() < target_dt:
                    pass

        # === 抢购 ===
        print("\n" + "=" * 50)
        print("🚀 抢购开始")
        print("=" * 50)

        # 1. 切换计费周期
        switch_billing_cycle(page, billing_cycle)

        # 2. 点击 Pro 订阅
        if not click_pro_subscribe(page):
            ss(page, "subscribe_failed")
            return

        # 3. 处理弹窗
        result = handle_flow(page)

        if result["status"] == "payment":
            print("\n🎉 已到达支付页面！请手动完成支付")
            ss(page, "payment_page")
        elif result["status"] == "login_required":
            print("\n❌ 需要登录。请重新登录 bigmodel.cn 后重试")
            ss(page, "login_required")
        elif result["status"] == "stuck":
            print(f"\n⚠️ {result['msg']}")
            ss(page, "final_state")
        else:
            print(f"\n⚠️ 未知状态: {result}")
            ss(page, "unknown_state")

        print("\n⏸️  浏览器保持 60 秒...")
        time.sleep(60)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        if page:
            ss(page, "error")
    finally:
        if context:
            context.close()
        pw.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GLM Coding Plan 抢购")
    parser.add_argument("--time", "-t", type=str, help="目标时间 'YYYY-MM-DD HH:MM:SS'")
    parser.add_argument("--now", "-n", action="store_true", help="测试模式")
    parser.add_argument("--cycle", type=str, default="monthly",
                        choices=["monthly", "quarterly", "yearly"])
    args = parser.parse_args()

    # 计费周期（模块级变量，在 main_flow 中使用）
    billing_cycle = args.cycle

    # 如果没传 --time 和 --now，尝试读 config
    target = args.time
    if not target and not args.now:
        config_file = SCRIPT_DIR / "sniper_config.json"
        if config_file.exists():
            cfg = json.loads(config_file.read_text(encoding="utf-8"))
            target = cfg.get("target_time")
            if cfg.get("billing_cycle"):
                billing_cycle = cfg["billing_cycle"]
            if target:
                print(f"📋 从 config 读取目标时间: {target}")
            else:
                print("⚠️ config 中未设置 target_time")
        if not target:
            parser.print_help()
            print("\n示例: python glm_sniper.py --time '2026-06-19 09:00:00'")
            sys.exit(1)

    main_flow(target_time=target if target else None, billing_cycle=billing_cycle)
