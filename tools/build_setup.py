"""Build the Windows setups with Inno Setup (installer/*.iss).

    uv run --group build python tools/build_setup.py user    dist/user/DevExAI-User-Setup.exe (after build_user.py)
    uv run --group build python tools/build_setup.py admin   dist/DevExAI-Admin-Setup-<ver>.exe (after build.py)

Inno Setup 6 is found on PATH, in its per-user folder or in Program Files.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devexai import __version__  # noqa: E402


def iscc() -> str:
    places = [shutil.which("ISCC"),
              *(str(Path(os.environ[v]) / sub / "Inno Setup 6" / "ISCC.exe")
                for v, sub in (("LOCALAPPDATA", "Programs"), ("ProgramFiles(x86)", ""), ("ProgramFiles", ""))
                if v in os.environ)]
    for place in places:
        if place and Path(place).is_file():
            return place
    sys.exit("Inno Setup 6 not found: winget install JRSoftware.InnoSetup")


def main(which: str) -> None:
    need = ROOT / "dist" / ("user/devexai.exe" if which == "user" else "devexai/devexai.exe")
    if not need.is_file():
        sys.exit(f"{need} is missing: run tools/{'build_user' if which == 'user' else 'build'}.py first")
    subprocess.run([iscc(), "/Q", f"/DVersion={__version__}", f"/DRoot={ROOT}", str(ROOT / "installer" / f"{which}.iss")],
                   check=True)
    print(f"Built the {which} setup in {ROOT / 'dist' / ('user' if which == 'user' else '')}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("user", "admin"):
        sys.exit(__doc__)
    main(sys.argv[1])
