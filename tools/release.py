"""Release signing. Keep the private key outside the repository and off shared drives.

    python tools/release.py keygen <private-key-file>
        Makes a new Ed25519 release key and prints the public line for src/devexai/update/keys.py.

    python tools/release.py sign --key <private-key-file> --zip dist/devexai-0.2.0-windows-x64.zip \\
                                 --url https://updates.example/v1/files/devexai-0.2.0-windows-x64.zip
        Writes latest.json next to the zip. Upload both; the server serves latest.json at
        <update url>/<platform>/latest.json to callers with a valid licence key.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from devexai.update.manifest import sign, verify  # noqa: E402

_ZIP = re.compile(r"devexai-(?P<version>[\d.]+)-(?P<platform>[a-z]+-[a-z0-9]+)\.zip")


def keygen(path: Path) -> None:
    if path.exists():
        sys.exit(f"{path} exists; not overwriting a key")
    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption()))
    public = key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    print(f"Private key: {path}\nAdd to RELEASE_KEYS in src/devexai/update/keys.py:\n"
          f'    "{base64.b64encode(public).decode()}",')


def sign_zip(key_path: Path, zip_path: Path, url: str) -> None:
    m = _ZIP.fullmatch(zip_path.name)
    if not m:
        sys.exit("zip name must be devexai-<version>-<platform>.zip (as tools/build.py makes it)")
    key = ser.load_pem_private_key(key_path.read_bytes(), password=None)
    data = zip_path.read_bytes()
    manifest = {"version": m["version"], "platform": m["platform"], "url": url,
                "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    envelope = sign(manifest, key)
    verify(envelope, (base64.b64encode(key.public_key().public_bytes(ser.Encoding.Raw,
                                                                      ser.PublicFormat.Raw)).decode(),))
    out = zip_path.with_name("latest.json")
    out.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    print(f"Wrote {out} for {m['version']} ({m['platform']})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="release")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen").add_argument("key", type=Path)
    s = sub.add_parser("sign")
    s.add_argument("--key", type=Path, required=True)
    s.add_argument("--zip", type=Path, required=True)
    s.add_argument("--url", required=True)
    args = parser.parse_args()
    if args.cmd == "keygen":
        keygen(args.key)
    else:
        sign_zip(args.key, args.zip, args.url)


if __name__ == "__main__":
    main()
