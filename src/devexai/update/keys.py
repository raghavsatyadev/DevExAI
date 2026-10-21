"""Public keys that may sign releases (Ed25519, raw 32 bytes, base64). Only the public half lives here.

The private half stays on the release machine, off the repository and shared drives. To rotate, add the
new key's line (`python tools/release.py keygen <file>` prints it), ship a release trusting both, then
drop the old one.
"""

RELEASE_KEYS: tuple[str, ...] = (
    "P8b7u6gMwsIMz7jWpSgomH2SyM3vigeKVCTrtFXwkB0=",  # release key, ~/.devexai-release/release-signing.key
)
