"""`python -m devexai_cli`, the packaged devexai.exe and the devexai.pyz zipapp all start here."""

import sys

from devexai_cli.cli import main

if __name__ == "__main__":
    sys.exit(main())
