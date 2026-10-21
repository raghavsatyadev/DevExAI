"""Build the developer command (src/devexai_cli) as one program file: dist/user/devexai.exe on Windows,
dist/user/devexai-linux-x64 on Linux. It must hold no admin code: the build fails if any devexai module
got in.

    uv run --group build python tools/build_user.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> Path:
    out, work = ROOT / "dist" / "user", ROOT / "build" / "user"
    shutil.rmtree(work, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    name = "devexai" if os.name == "nt" else "devexai-linux-x64"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
                    "--name", name, "--distpath", str(out), "--workpath", str(work), "--specpath", str(work),
                    "--paths", str(ROOT / "src"), "--exclude-module", "devexai", "--exclude-module", "cryptography",
                    "--icon", str(ROOT / "assets" / "logo" / "devexai.ico"),
                    str(ROOT / "src" / "devexai_cli" / "__main__.py")], check=True, cwd=ROOT)
    toc = (work / name / "PYZ-00.toc").read_text(encoding="utf-8")
    if leaked := sorted(set(re.findall(r"'(devexai(?:\.[\w.]+)?)'", toc))):
        sys.exit(f"admin code got into the developer command: {', '.join(leaked)}")
    exe = out / (name + (".exe" if os.name == "nt" else ""))
    print(f"Built {exe} ({exe.stat().st_size // 1_000_000} MB)")
    return exe


if __name__ == "__main__":
    main()
