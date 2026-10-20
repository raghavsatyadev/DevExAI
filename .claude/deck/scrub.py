"""Clear author fields PowerPoint writes on save: python scrub.py <deck.pptx>
Run after anim.ps1 so the shared deck carries no personal names."""
import os
import re
import sys
import zipfile

EMPTY = ("dc:creator", "cp:lastModifiedBy", "dc:description")


def scrub(xml):
    for tag in EMPTY:
        xml = re.sub(rf"<{tag}>[^<]*</{tag}>", f"<{tag}/>", xml)
    return xml


path = sys.argv[1]
tmp = path + ".tmp"
with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
    for item in src.infolist():
        data = src.read(item.filename)
        if item.filename == "docProps/core.xml":
            data = scrub(data.decode("utf-8")).encode("utf-8")
        dst.writestr(item, data)
os.replace(tmp, path)
print("scrubbed", path)
