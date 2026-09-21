"""Create a native one-folder distribution on the current operating system."""

from pathlib import Path
import os
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
source_files = [path for path in ROOT.glob("*.docx") if path.name.startswith("ราคากลางงานจัดซื้อพัสดุ ") and not path.name.startswith("~$")]
frontend = ROOT / "frontend" / "dist"
if len(source_files) != 1 or not (frontend / "index.html").is_file():
    raise SystemExit("ต้องมี DOCX ต้นฉบับหนึ่งไฟล์และ frontend/dist; รัน npm ci และ npm run build ใน frontend ก่อน")

command = [
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
    "--name", "QuotationLocal", "--add-data", f"{source_files[0]}{os.pathsep}.",
    "--add-data", f"{frontend}{os.pathsep}frontend/dist",
    "--add-data", f"{ROOT / 'frontend' / 'public' / 'fonts'}{os.pathsep}frontend/public/fonts",
    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT), str(ROOT / "run.py"),
]
subprocess.run(command, cwd=ROOT, check=True)
destination = ROOT / "dist" / "QuotationLocal"
examples = destination / "examples"
examples.mkdir(exist_ok=True)
for name in ("ต้นฉบับ สายช่างโยธา 70.docx", "ต้นฉบับ สายพลาธิการ 69.docx"):
    path = ROOT / name
    if path.is_file():
        shutil.copy2(path, examples / name)
shutil.copy2(ROOT / "README.md", destination / "README.md")
print(f"พร้อมใช้งานที่ {destination}")
