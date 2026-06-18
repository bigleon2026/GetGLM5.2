"""
从运行中的 Chrome 通过 CDP 提取 bigmodel.cn cookies
用法：先以调试模式启动 Chrome，然后运行此脚本
"""

# 方法1：尝试从已打开的 Chrome 提取（如果用了 --remote-debugging-port）
# 方法2：自动启动 Chrome 调试模式

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request

SCRIPT_DIR = Path(__file__).parent
COOKIES_FILE = SCRIPT_DIR / "cookies_bigmodel.json"
DEBUG_PORT = 9222
TARGET_DOMAIN = "bigmodel.cn"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def get_cookies_via_cdp(port: int) -> list:
    """通过 Chrome DevTools Protocol 获取 cookies"""
    # 获取页面列表
    resp = urlopen(f"http://127.0.0.1:{port}/json")
    pages = json.loads(resp.read())

    print(f"  找到 {len(pages)} 个页面")

    # 找一个 bigmodel.cn 的页面
    target_page = None
    for p in pages:
        if TARGET_DOMAIN in p.get("url", ""):
            target_page = p
            break

    if not target_page:
        # 没有现成的页面，需要导航到一个
        print(f"  未找到 {TARGET_DOMAIN} 页面，将打开新页面...")
        # 用 CDP 创建新页面
        ws_url = pages[0]["webSocketDebuggerUrl"] if pages else None
        if not ws_url:
            raise RuntimeError("没有可用的调试页面")
        return []  # 需要 WebSocket 连接，暂时跳过

    # 通过 HTTP 端点（较新的 Chrome 支持）
    ws_url = target_page["webSocketDebuggerUrl"]
    print(f"  目标页面: {target_page['url']}")

    # 使用 CDP Network.getCookies
    import websocket
    ws = websocket.create_connection(ws_url)

    # 获取 cookies
    ws.send(json.dumps({
        "id": 1,
        "method": "Network.getCookies",
        "params": {"urls": [f"https://{TARGET_DOMAIN}/"]}
    }))
    response = json.loads(ws.recv())
    ws.close()

    cookies_data = response.get("result", {}).get("cookies", [])
    print(f"  获取到 {len(cookies_data)} 个 cookies")

    # 转换为 Playwright 格式
    cookies = []
    for c in cookies_data:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
        }
        if "expires" in c and c["expires"] > 0:
            cookie["expires"] = c["expires"]
        cookies.append(cookie)

    return cookies


def check_debug_port(port: int) -> bool:
    """检查 Chrome 调试端口是否可用"""
    try:
        resp = urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
        data = json.loads(resp.read())
        print(f"  ✅ Chrome 调试端口 {port} 可用: {data.get('Browser', 'unknown')}")
        return True
    except Exception:
        return False


def launch_chrome_debug():
    """启动 Chrome 调试模式"""
    print(f"🚀 启动 Chrome 调试模式 (端口 {DEBUG_PORT})...")
    subprocess.Popen(
        [CHROME_PATH, f"--remote-debugging-port={DEBUG_PORT}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # 等待 Chrome 启动
    for i in range(10):
        time.sleep(1)
        if check_debug_port(DEBUG_PORT):
            return True
        print(f"  等待 Chrome 启动... ({i+1}/10)")
    return False


def main():
    print("=" * 50)
    print("  bigmodel.cn Cookies 导出 (CDP 方式)")
    print("=" * 50)

    # 检查是否已经有调试端口
    if not check_debug_port(DEBUG_PORT):
        print("\n⚠️  需要以调试模式重启 Chrome")
        print("   将自动启动 Chrome 调试模式...")
        print("   ⚠️  这会打开一个新的 Chrome 窗口\n")

        if not launch_chrome_debug():
            print("\n❌ 无法启动 Chrome 调试模式")
            print("\n手动方式：")
            print(f'  1. 关闭所有 Chrome 窗口')
            print(f'  2. Win+R 运行: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
            print(f'  3. 重新运行本脚本')
            sys.exit(1)

    try:
        cookies = get_cookies_via_cdp(DEBUG_PORT)
    except Exception as e:
        print(f"\n❌ 获取 cookies 失败: {e}")
        print("\n尝试手动方式：")
        print("1. 在 Chrome 地址栏打开: chrome://settings/cookies")
        print("2. 搜索 bigmodel.cn")
        print("3. 或者直接重新运行 export_cookies.py (需要关闭 Chrome)")
        sys.exit(1)

    if not cookies:
        print("\n❌ 未找到 bigmodel.cn 的 cookies。请确保已登录。")
        sys.exit(1)

    # 保存
    from datetime import datetime
    output = {
        "cookies": cookies,
        "exported_at": datetime.now().isoformat(),
        "domain": TARGET_DOMAIN,
        "count": len(cookies),
    }
    COOKIES_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 成功导出 {len(cookies)} 个 cookies 到: {COOKIES_FILE}")
    key_names = [c["name"] for c in cookies]
    print(f"   Cookie 名称: {key_names}")


if __name__ == "__main__":
    main()
