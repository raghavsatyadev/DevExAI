"""Build the packaged program for this machine's platform: dist/devexai/ and dist/devexai-<ver>-<platform>.zip.

    uv run --group build python tools/build.py

The build is unsigned until we have a code-signing certificate (Windows SmartScreen may warn).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devexai import __version__  # noqa: E402
from devexai.update.manifest import platform_tag  # noqa: E402


# One analysis, two programs sharing one folder: devexai.exe for the terminal and devexaiw.exe, which has
# no console window and runs as an icon in the notification area (the Start menu entry starts it).
# Off Windows only devexai is built.
SPEC = """
import sys
from PyInstaller.utils.hooks import collect_submodules

a = Analysis([{entry!r}], pathex=[{src!r}],
             hiddenimports=collect_submodules("devexai") + collect_submodules("devexai_cli")
             + collect_submodules("slack_sdk"),  # imported lazily
             # the dashboard hands out at /get: the developer builds (user/) and devexai.pyz, made from the
             # developer command's source (devexai_cli_src/)
             datas=[({settings!r}, "."), ({icon!r}, "assets/logo"), ({cli!r}, "devexai_cli_src"), *{user!r}])
pyz = PYZ(a.pure)
console = EXE(pyz, a.scripts, [], exclude_binaries=True, name="devexai", console=True, icon={icon!r})
programs = [console]
if sys.platform == "win32":  # the tray icon is Windows-only
    programs.append(EXE(pyz, a.scripts, [], exclude_binaries=True, name="devexaiw", console=False, icon={icon!r}))
COLLECT(*programs, a.binaries, a.datas, name="devexai")
"""


def user_files() -> list[tuple[str, str]]:
    """The developer builds made so far (tools/build_user.py, tools/build_setup.py user; the Linux one in Docker)."""
    found = [ROOT / "dist" / "user" / name for name in ("DevExAI-User-Setup.exe", "devexai-linux-x64")]
    for path in found:
        print(f"{'with' if path.is_file() else 'WITHOUT'} {path.name}")
    return [(str(p), "user") for p in found if p.is_file()]


def main() -> None:
    dist, work = ROOT / "dist", ROOT / "build"
    shutil.rmtree(dist / "devexai", ignore_errors=True)
    work.mkdir(exist_ok=True)
    spec = work / "devexai.spec"
    spec.write_text(SPEC.format(entry=str(ROOT / "tools" / "entry.py"), src=str(ROOT / "src"),
                                settings=str(ROOT / "settings.example.toml"),
                                icon=str(ROOT / "assets" / "logo" / "devexai.ico"),
                                cli=str(ROOT / "src" / "devexai_cli"), user=user_files()), encoding="utf-8")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(dist), "--workpath", str(work), str(spec)], check=True, cwd=ROOT)
    out = dist / f"devexai-{__version__}-{platform_tag()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted((dist / "devexai").rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(dist).as_posix())
    print(f"Built {out} ({out.stat().st_size // 1_000_000} MB)")


if __name__ == "__main__":
    main()
