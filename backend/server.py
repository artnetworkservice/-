"""Small local HTTP API and static frontend server."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import binascii
import hashlib
import io
import json
import mimetypes
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from urllib.parse import parse_qs, urlparse
import uuid
import zipfile

from .document import ENGINE_REVISION, create_docx, convert_to_pdf
from .pricing import ValidationError, calculate_document, format_money
from .storage import Store


ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
FRONTEND = ROOT / "frontend" / "dist"
STORE = Store()


def serializable(value):
    from decimal import Decimal
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [serializable(x) for x in value]
    if isinstance(value, dict):
        return {key: serializable(x) for key, x in value.items()}
    return value


def export_document(document_id: str, format_name: str) -> Path:
    record = STORE.get_document(document_id)
    if not record or record["deleted_at"]:
        raise KeyError("ไม่พบเอกสาร")
    template = STORE.template_version(record["template_version_id"])
    if not template:
        raise RuntimeError("ไม่พบแม่แบบเวอร์ชันของเอกสาร")
    revision = hashlib.sha256((ENGINE_REVISION + record["data_json"] + record["template_version_id"]).encode("utf-8")).hexdigest()[:16]
    folder = STORE.root / "exports"
    docx = folder / f"{document_id}-{revision}.docx"
    if not docx.exists():
        create_docx(record["data"], docx, source_path=Path(template["source_path"]), blocks=template["blocks"])
    if format_name == "docx":
        return docx
    if format_name == "pdf":
        pdf = folder / f"{document_id}-{revision}.pdf"
        if not pdf.exists():
            convert_to_pdf(docx, pdf)
        return pdf
    raise ValueError("รองรับเฉพาะ docx และ pdf")


def backup_bytes() -> bytes:
    with tempfile.TemporaryDirectory(prefix="quotation-backup-") as temporary:
        db_copy = Path(temporary) / "quotation.sqlite3"
        with STORE.connect() as source, sqlite3.connect(db_copy) as target:
            source.backup(target)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_copy, "quotation.sqlite3")
            for file in (STORE.root / "templates").glob("*.docx"):
                archive.write(file, f"templates/{file.name}")
        return buffer.getvalue()


def restore_backup(payload: bytes) -> None:
    with tempfile.TemporaryDirectory(prefix="quotation-restore-") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            if "quotation.sqlite3" not in names or any(name.startswith("/") or ".." in Path(name).parts for name in names):
                raise ValueError("ไฟล์สำรองไม่ถูกต้อง")
            archive.extractall(target)
        db_file = target / "quotation.sqlite3"
        with sqlite3.connect(db_file) as db:
            ok = db.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise ValueError("ฐานข้อมูลสำรองเสียหาย")
            rows = db.execute("SELECT id,source_path FROM template_versions").fetchall()
            for version_id, _ in rows:
                file = target / "templates" / f"{version_id}.docx"
                if not file.exists():
                    raise ValueError("ไฟล์แม่แบบในชุดสำรองไม่ครบ")
                db.execute("UPDATE template_versions SET source_path=? WHERE id=?", (str(STORE.root / "templates" / file.name), version_id))
            db.commit()
        # Leave a local rollback snapshot before replacing the live database.
        rollback = STORE.root / "quotation-before-restore.sqlite3"
        with STORE.connect() as source, sqlite3.connect(rollback) as target_db:
            source.backup(target_db)
        for file in (target / "templates").glob("*.docx"):
            (STORE.root / "templates" / file.name).write_bytes(file.read_bytes())
        with sqlite3.connect(db_file) as source, STORE.connect() as target_db:
            source.backup(target_db)


class Handler(BaseHTTPRequestHandler):
    server_version = "QuotationLocal/1.1"

    def _json(self, status: int, payload) -> None:
        data = json.dumps(serializable(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path, mime: str, name: str | None = None) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if name:
            from urllib.parse import quote
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(name)}")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 15_000_000:
            raise ValueError("ข้อมูลที่ส่งมีขนาดใหญ่เกินไป")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        try:
            if method == "GET" and path == "/api/health":
                return self._json(200, {"ok": True})
            if method == "GET" and path == "/api/templates":
                return self._json(200, STORE.list_templates())
            if method == "POST" and path == "/api/templates":
                body = self._body()
                return self._json(201, STORE.create_template(str(body.get("name") or "").strip(), str(body.get("base_template_id") or "")))
            if method == "POST" and path == "/api/templates/import":
                body = self._body()
                try:
                    content = base64.b64decode(str(body.get("content_base64") or ""), validate=True)
                except binascii.Error as exc:
                    raise ValueError("ไฟล์แม่แบบไม่ถูกต้อง") from exc
                return self._json(201, STORE.import_template(str(body.get("name") or ""), content))
            match = re.fullmatch(r"/api/templates/([^/]+)/versions", path)
            if match and method == "GET":
                return self._json(200, STORE.list_template_versions(match.group(1)))
            match = re.fullmatch(r"/api/templates/([^/]+)/activate", path)
            if match and method == "POST":
                STORE.activate_template_version(match.group(1), str(self._body().get("version_id") or ""))
                return self._json(200, STORE.current_template(match.group(1)))
            match = re.fullmatch(r"/api/templates/([^/]+)", path)
            if match and method == "GET":
                record = STORE.current_template(match.group(1))
                if not record:
                    raise KeyError("ไม่พบแม่แบบ")
                return self._json(200, record)
            if match and method == "PUT":
                body = self._body()
                return self._json(200, STORE.update_template(match.group(1), str(body.get("name") or ""), body.get("blocks") or {}))
            if match and method == "DELETE":
                STORE.delete_template(match.group(1))
                return self._json(200, {"ok": True})
            if method == "GET" and path == "/api/documents":
                return self._json(200, STORE.list_documents(query.get("q", [""])[0], include_deleted=query.get("trash", [""])[0] == "1"))
            if method == "POST" and path == "/api/documents":
                return self._json(201, STORE.save_document(self._body()))
            if method == "POST" and path == "/api/documents/validate":
                return self._json(200, calculate_document(self._body()))
            match = re.fullmatch(r"/api/documents/([^/]+)/duplicate", path)
            if match and method == "POST":
                return self._json(201, STORE.duplicate_document(match.group(1)))
            match = re.fullmatch(r"/api/documents/([^/]+)/restore", path)
            if match and method == "POST":
                STORE.set_deleted(match.group(1), False)
                return self._json(200, {"ok": True})
            match = re.fullmatch(r"/api/documents/([^/]+)/export/(docx|pdf)", path)
            if match and method == "GET":
                document_id, format_name = match.groups()
                file = export_document(document_id, format_name)
                record = STORE.get_document(document_id)
                name = (record["subject"] if record else "ราคากลาง").replace("/", "-")[:80] + "." + format_name
                return self._file(file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if format_name == "docx" else "application/pdf", None if query.get("inline") else name)
            match = re.fullmatch(r"/api/documents/([^/]+)", path)
            if match and method == "GET":
                record = STORE.get_document(match.group(1))
                if not record:
                    raise KeyError("ไม่พบเอกสาร")
                return self._json(200, record)
            if match and method == "PUT":
                return self._json(200, STORE.save_document(self._body(), document_id=match.group(1)))
            if match and method == "DELETE":
                STORE.set_deleted(match.group(1), True)
                return self._json(200, {"ok": True})
            if method == "GET" and path == "/api/vendors":
                return self._json(200, STORE.search_vendors(query.get("q", [""])[0]))
            if method == "GET" and path == "/api/backup":
                data = backup_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", 'attachment; filename="quotation-backup.zip"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            if method == "POST" and path == "/api/restore":
                length = int(self.headers.get("Content-Length", "0"))
                if length > 50_000_000:
                    raise ValueError("ไฟล์สำรองใหญ่เกินไป")
                restore_backup(self.rfile.read(length))
                return self._json(200, {"ok": True})
            if method == "GET" and not path.startswith("/api/"):
                return self._static(path)
            self._json(404, {"error": "ไม่พบหน้าที่ต้องการ"})
        except (ValidationError, ValueError) as exc:
            self._json(400, {"error": str(exc)})
        except KeyError as exc:
            self._json(404, {"error": str(exc).strip("'")})
        except (RuntimeError, OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
            self._json(500, {"error": str(exc)})

    def _static(self, path: str) -> None:
        if not FRONTEND.exists():
            return self._json(503, {"error": "ยังไม่ได้ build หน้าเว็บ: ไปที่ frontend แล้วรัน npm run build"})
        file = (FRONTEND / path.lstrip("/")).resolve()
        if not file.is_relative_to(FRONTEND.resolve()) or not file.is_file():
            file = FRONTEND / "index.html"
        self._file(file, mimetypes.guess_type(file)[0] or "application/octet-stream")

    def do_GET(self) -> None: self._dispatch("GET")
    def do_POST(self) -> None: self._dispatch("POST")
    def do_PUT(self) -> None: self._dispatch("PUT")
    def do_DELETE(self) -> None: self._dispatch("DELETE")


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"QuotationLocal: http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run()
