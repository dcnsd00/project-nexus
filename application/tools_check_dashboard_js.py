"""Syntax-check inline JavaScript in dashboard and wallet HTML when Node is present."""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
import shutil, subprocess, tempfile

class ScriptExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.active=False; self.parts=[]; self.scripts=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="script": self.active=True; self.parts=[]
    def handle_endtag(self, tag):
        if tag.lower()=="script" and self.active:
            self.scripts.append("".join(self.parts)); self.active=False
    def handle_data(self, data):
        if self.active: self.parts.append(data)

def main(root: Path) -> int:
    node=shutil.which("node")
    if not node:
        print("SKIP: Node.js not installed; JavaScript syntax was not checked.")
        return 0
    total=0
    with tempfile.TemporaryDirectory(prefix="nexus-js-") as tmp:
        for name in ("dashboard.html", "wallet.html"):
            parser=ScriptExtractor(); parser.feed((root/name).read_text(encoding="utf-8"))
            for index, source in enumerate(parser.scripts):
                if not source.strip(): continue
                path=Path(tmp)/f"{name}-{index}.js"; path.write_text(source,encoding="utf-8")
                subprocess.run([node,"--check",str(path)],check=True,capture_output=True,text=True)
                total+=1
            print(f"PASS: {name} ({len(parser.scripts)} inline script blocks)")
    print(f"PASS: {total} JavaScript blocks checked")
    return 0

if __name__ == "__main__":
    import sys
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
