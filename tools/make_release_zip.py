"""Create a Windows Explorer compatible source ZIP with ASCII-only paths."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PREFIX = PurePosixPath("QuotationLocal-v1.1")


def archive_name(path: Path) -> PurePosixPath:
    name = path.name
    if name.startswith("ราคากลางงานจัดซื้อพัสดุ ") and name.endswith(".docx"):
        return PurePosixPath("base-template.docx")
    if name == "ต้นฉบับ สายช่างโยธา 70.docx":
        return PurePosixPath("examples/civil-engineering-template-70.docx")
    if name == "ต้นฉบับ สายพลาธิการ 69.docx":
        return PurePosixPath("examples/quartermaster-template-69.docx")
    return PurePosixPath(path.as_posix())


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw]


def create_archive(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    names: set[str] = set()
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in tracked_files():
            source = ROOT / relative
            if not source.is_file():
                continue
            mapped = PREFIX / archive_name(relative)
            mapped_text = mapped.as_posix()
            if not mapped_text.isascii():
                raise ValueError(f"ชื่อไฟล์ใน ZIP ต้องเป็น ASCII: {mapped_text}")
            if mapped_text in names:
                raise ValueError(f"ชื่อไฟล์ใน ZIP ซ้ำ: {mapped_text}")
            names.add(mapped_text)
            info = ZipInfo(mapped_text)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            archive.writestr(info, source.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    create_archive(parser.parse_args().destination.resolve())
