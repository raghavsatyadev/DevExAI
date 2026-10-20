"""Build the packaged program for this machine's platform: dist/devexai/ and dist/devexai-<ver>-<platform>.zip.

    uv run --group build python tools/build.py

The build is unsigned until we have a code-signing certificate (Windows SmartScreen may warn).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devexai import __version__  # noqa: E402
from devexai.update.manifest import platform_tag  # noqa: E402


def main() -> None:
    dist, work = ROOT / "dist", ROOT / "build"
    shutil.rmtree(dist / "devexai", ignore_errors=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
        "--name", "devexai", "--distpath", str(dist), "--workpath", str(work), "--specpath", str(work),
        "--paths", str(ROOT / "src"), "--collect-submodules", "devexai",
        "--add-data", f"{ROOT / 'settings.example.toml'}{os.pathsep}.",
        str(ROOT / "tools" / "entry.py"),
    ], check=True, cwd=ROOT)
    out = dist / f"devexai-{__version__}-{platform_tag()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted((dist / "devexai").rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(dist).as_posix())
    print(f"Built {out} ({out.stat().st_size // 1_000_000} MB)")


if __name__ == "__main__":
    main()
