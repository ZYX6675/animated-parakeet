"""Test adapter that deliberately loses data: drops the last paragraph of a DOCX, copies others."""
import re
import shutil
import sys
import zipfile

src, dst = sys.argv[1], sys.argv[2]
if not src.endswith(".docx"):
    shutil.copy(src, dst)
    sys.exit(0)
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "word/document.xml":
            text = data.decode()
            idx = text.rfind("<w:p>")
            end = text.find("</w:p>", idx) + len("</w:p>")
            data = (text[:idx] + text[end:]).encode()
        zout.writestr(item.filename, data)
