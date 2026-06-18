"""
从 Chrome 导出 bigmodel.cn 的 cookies 为 Playwright 兼容格式
用法: python export_cookies.py
输出: cookies_bigmodel.json
"""
import os
import sys
import json
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# Chrome cookie 数据库路径
CHROME_USER_DATA = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
# 也尝试 Edge
EDGE_USER_DATA = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"

TARGET_DOMAIN = "bigmodel.cn"
OUTPUT_FILE = Path(__file__).parent / "cookies_bigmodel.json"


def decrypt_chrome_cookies(cookies_db_path: Path):
    """从 Chrome cookies SQLite 数据库读取并解密 cookies"""
    try:
        import win32crypt
    except ImportError:
        print("需要 pywin32 库，正在尝试安装...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
        import win32crypt

    # Chrome 运行时数据库被锁定，先复制一份
    temp_db = cookies_db_path.parent / f"_temp_cookies_{os.getpid()}.db"
    shutil.copy2(cookies_db_path, temp_db)

    try:
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()

        # 查找所有 bigmodel.cn 相关 cookies
        cursor.execute("""
            SELECT host_key, name, encrypted_value, path, expires_utc, is_secure, is_httponly
            FROM cookies
            WHERE host_key LIKE ?
        """, (f"%{TARGET_DOMAIN}%",))

        cookies = []
        for row in cursor.fetchall():
            host_key, name, encrypted_value, path, expires_utc, is_secure, is_httponly = row
            try:
                # 用 Windows DPAPI 解密
                value = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode("utf-8")
            except Exception:
                # 可能未加密或解密失败，尝试直接使用
                try:
                    value = encrypted_value.decode("utf-8")
                except Exception:
                    continue

            cookie = {
                "name": name,
                "value": value,
                "domain": host_key.lstrip("."),
                "path": path,
                "secure": bool(is_secure),
                "httpOnly": bool(is_httponly),
            }
            if expires_utc and expires_utc > 0:
                cookie["expires"] = expires_utc / 1000000 - 11644473600  # Chrome time -> unix time

            cookies.append(cookie)

        conn.close()
        return cookies

    finally:
        temp_db.unlink(missing_ok=True)


def export_from_browser(user_data_dir: Path, browser_name: str) -> list:
    """从指定浏览器导出 cookies"""
    cookies_db = user_data_dir / "Default" / "Network" / "Cookies"
    if not cookies_db.exists():
        # 尝试 Profile 1 等
        for profile in user_data_dir.iterdir():
            if profile.is_dir() and profile.name.startswith("Profile"):
                db = profile / "Network" / "Cookies"
                if db.exists():
                    cookies_db = db
                    break
        else:
            print(f"  [{browser_name}] Cookies 文件不存在: {cookies_db}")
            return []

    print(f"  [{browser_name}] 找到 Cookies: {cookies_db}")
    try:
        cookies = decrypt_chrome_cookies(cookies_db)
        print(f"  [{browser_name}] 解密成功，找到 {len(cookies)} 个相关 cookie")
        return cookies
    except Exception as e:
        print(f"  [{browser_name}] 解密失败: {e}")
        return []


def main():
    print("=" * 50)
    print("  bigmodel.cn Cookies 导出工具")
    print("=" * 50)

    # 确保 Chrome 已关闭，否则数据库被锁定
    print("\n⚠️  注意：请先关闭 Chrome/Edge 浏览器，否则无法读取 Cookies")
    print("   如果浏览器正在运行，按 Ctrl+C 退出，关闭浏览器后重试\n")

    # 尝试 Chrome
    cookies = []
    if CHROME_USER_DATA.exists():
        cookies = export_from_browser(CHROME_USER_DATA, "Chrome")

    # 如果 Chrome 没有，尝试 Edge
    if not cookies and EDGE_USER_DATA.exists():
        cookies = export_from_browser(EDGE_USER_DATA, "Edge")

    if not cookies:
        print("\n❌ 未找到 bigmodel.cn 的 cookies。请确保：")
        print("  1. 已用 Chrome 登录 bigmodel.cn")
        print("  2. 浏览器已关闭")
        sys.exit(1)

    # 保存为 Playwright 兼容格式
    output = {
        "cookies": cookies,
        "exported_at": datetime.now().isoformat(),
        "domain": TARGET_DOMAIN,
        "count": len(cookies),
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 成功导出 {len(cookies)} 个 cookies 到: {OUTPUT_FILE}")

    # 检查关键 cookie
    key_names = [c["name"] for c in cookies]
    important = ["token", "session", "auth", "login", "sid", "JSESSIONID"]
    found_important = [n for n in important if any(n.lower() in k.lower() for k in key_names)]
    if found_important:
        print(f"   关键 cookie 名称包含: {found_important}")
    print(f"   全部 cookie 名称: {key_names}")


if __name__ == "__main__":
    main()
