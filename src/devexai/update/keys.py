"""Public keys that may sign releases (Ed25519, raw 32 bytes, base64). Only the public half lives here.

DEVELOPMENT KEY: replace it with the real release key before shipping to a customer
(`python tools/release.py keygen <file outside the repo>` prints the line to paste).
"""

RELEASE_KEYS: tuple[str, ...] = (
    "luSV0xoXfzxgecfnxXyHBw4ULY7sj/6kX2Pdo9tIEkc=",  # dev key, ~/.devexai-release/dev-signing.key
)
