"""devexai for developers: install DevExAI tools into a project or your home folder, and remove them.

    devexai install <tool>              into this project (the current folder; commit the files for the team)
    devexai install <tool> --global     into your home folder, for every project
    devexai uninstall <tool> [--global]
    devexai list                        the published tools
    devexai connect https://<server>    remember the DevExAI server and trust its certificate (setup does this)
    devexai update                      install a newer devexai from that server

Its own package, Python standard library only, importing nothing from the DevExAI server (`devexai`):
the developer build ships this and nothing else. A test checks the imports.
"""

__version__ = "0.1.2"
