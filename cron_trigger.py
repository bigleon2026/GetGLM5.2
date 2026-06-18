"""
GLM Sniper cron trigger
Reads sniper_config.json and runs glm_sniper.py
"""
import subprocess
import sys
from pathlib import Path

SNIPER_DIR = Path(r"F:\Git\GetGLM5.2")

def main():
    print(f"Running sniper from {SNIPER_DIR}")
    result = subprocess.run(
        [sys.executable, str(SNIPER_DIR / "glm_sniper.py")],
        cwd=str(SNIPER_DIR),
        capture_output=True,
        text=True,
        timeout=600,  # 10 min max
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:2000])
    print(f"Exit code: {result.returncode}")

if __name__ == "__main__":
    main()
