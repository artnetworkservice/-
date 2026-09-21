"""SQLite persistence for a single-user local app."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from difflib import SequenceMatcher
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid
from typing import Any

from docx import Document

from .document import DEFAULT_SOURCE, _default_blocks, default_blocks


def data_dir() -> Path:
    configured = os.environ.get("QUOTATION_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "QuotationLocal"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "QuotationLocal"
    return Path.home() / ".local" / "share" / "quotation-local"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "templates").mkdir(exist_ok=True)
        (self.root / "exports").mkdir(exist_ok=True)
        self.db_path = self.root / "quotation.sqlite3"
        self._init()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS templates (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    active_version_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT
                );
                CREATE TABLE IF NOT EXISTS template_versions (
                    id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL REFERENCES templates(id),
                    version INTEGER NOT NULL,
                    source_path TEXT NOT NULL,
                    blocks_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(template_id, version)
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    template_version_id TEXT NOT NULL REFERENCES template_versions(id),
                    subject TEXT NOT NULL,
                    document_number TEXT NOT NULL,
                    document_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at DESC);
                CREATE TABLE IF NOT EXISTS vendors (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    normalized TEXT NOT NULL UNIQUE,
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(templates)")}
            if "deleted_at" not in columns:
                db.execute("ALTER TABLE templates ADD COLUMN deleted_at TEXT")
            if not db.execute("SELECT 1 FROM templates LIMIT 1").fetchone():
                template_id = str(uuid.uuid4())
                version_id = str(uuid.uuid4())
                source = self.root / "templates" / f"{version_id}.docx"
                shutil.copy2(DEFAULT_SOURCE, source)
                timestamp = now()
                db.execute(
                    "INSERT INTO templates(id,name,active_version_id,created_at,updated_at) VALUES (?,?,?,?,?)",
                    (template_id, "บันทึกราคากลางพัสดุ", version_id, timestamp, timestamp),
                )
                db.execute(
                    "INSERT INTO template_versions VALUES (?,?,?,?,?,?)",
                    (version_id, template_id, 1, str(source), json.dumps(default_blocks(), ensure_ascii=False), timestamp),
                )

    def list_templates(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT t.*, v.version, v.blocks_json FROM templates t
                   JOIN template_versions v ON v.id=t.active_version_id
                   WHERE t.deleted_at IS NULL ORDER BY t.updated_at DESC"""
            ).fetchall()
        return [{**dict(row), "blocks": json.loads(row["blocks_json"])} for row in rows]

    def template_version(self, version_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM template_versions WHERE id=?", (version_id,)).fetchone()
        return {**dict(row), "blocks": json.loads(row["blocks_json"])} if row else None

    def current_template(self, template_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT v.*, t.name FROM templates t JOIN template_versions v ON v.id=t.active_version_id WHERE t.id=?",
                (template_id,),
            ).fetchone()
        return {**dict(row), "blocks": json.loads(row["blocks_json"])} if row else None

    def create_template(self, name: str, base_template_id: str) -> dict[str, Any]:
        base = self.current_template(base_template_id)
        if not base:
            raise KeyError("ไม่พบแม่แบบต้นทาง")
        template_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        source = self.root / "templates" / f"{version_id}.docx"
        shutil.copy2(base["source_path"], source)
        timestamp = now()
        with self.connect() as db:
            db.execute("INSERT INTO templates(id,name,active_version_id,created_at,updated_at) VALUES (?,?,?,?,?)", (template_id, name, version_id, timestamp, timestamp))
            db.execute(
                "INSERT INTO template_versions VALUES (?,?,?,?,?,?)",
                (version_id, template_id, 1, str(source), base["blocks_json"], timestamp),
            )
        return self.current_template(template_id)  # type: ignore[return-value]

    def import_template(self, name: str, content: bytes) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("กรุณาระบุชื่อแม่แบบ")
        try:
            source_document = Document(BytesIO(content))
            blocks = _default_blocks(source_document)
        except Exception as exc:
            raise ValueError("ไฟล์ Word ไม่ใช่แม่แบบที่รองรับ: ต้องมีหัวเอกสาร รายการตัวอย่าง ข้อสรุป และจุดลงชื่อ") from exc
        template_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
        source = self.root / "templates" / f"{version_id}.docx"
        source.write_bytes(content)
        timestamp = now()
        with self.connect() as db:
            db.execute("INSERT INTO templates(id,name,active_version_id,created_at,updated_at) VALUES (?,?,?,?,?)",
                       (template_id, name.strip(), version_id, timestamp, timestamp))
            db.execute("INSERT INTO template_versions VALUES (?,?,?,?,?,?)",
                       (version_id, template_id, 1, str(source), json.dumps(blocks, ensure_ascii=False), timestamp))
        return self.current_template(template_id)  # type: ignore[return-value]

    def delete_template(self, template_id: str) -> None:
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM templates WHERE id=? AND deleted_at IS NULL", (template_id,)).fetchone()
            if not exists:
                raise KeyError("ไม่พบแม่แบบ")
            remaining = db.execute("SELECT COUNT(*) FROM templates WHERE deleted_at IS NULL").fetchone()[0]
            if remaining <= 1:
                raise ValueError("ต้องเหลือแม่แบบที่ใช้งานอย่างน้อย 1 รายการ")
            db.execute("UPDATE templates SET deleted_at=?,updated_at=? WHERE id=?", (now(), now(), template_id))

    def update_template(self, template_id: str, name: str, blocks: dict[str, str]) -> dict[str, Any]:
        current = self.current_template(template_id)
        if not current:
            raise KeyError("ไม่พบแม่แบบ")
        if not name.strip():
            raise ValueError("กรุณาระบุชื่อแม่แบบ")
        clean = current["blocks"].copy()
        for key in clean:
            if key in blocks:
                clean[key] = str(blocks[key])
        version_id = str(uuid.uuid4())
        source = self.root / "templates" / f"{version_id}.docx"
        shutil.copy2(current["source_path"], source)
        timestamp = now()
        with self.connect() as db:
            db.execute(
                "INSERT INTO template_versions VALUES (?,?,?,?,?,?)",
                (version_id, template_id, current["version"] + 1, str(source), json.dumps(clean, ensure_ascii=False), timestamp),
            )
            db.execute(
                "UPDATE templates SET name=?, active_version_id=?, updated_at=? WHERE id=?",
                (name.strip(), version_id, timestamp, template_id),
            )
        return self.current_template(template_id)  # type: ignore[return-value]

    def list_template_versions(self, template_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,version,created_at FROM template_versions WHERE template_id=? ORDER BY version DESC",
                (template_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def activate_template_version(self, template_id: str, version_id: str) -> None:
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM template_versions WHERE template_id=? AND id=?", (template_id, version_id)).fetchone()
            if not exists:
                raise KeyError("ไม่พบเวอร์ชันแม่แบบ")
            db.execute("UPDATE templates SET active_version_id=?,updated_at=? WHERE id=?", (version_id, now(), template_id))

    def list_documents(self, query: str = "", *, include_deleted: bool = False) -> list[dict[str, Any]]:
        sql = """SELECT d.id,d.template_version_id,d.subject,d.document_number,d.document_date,d.status,
                        d.created_at,d.updated_at,d.deleted_at,t.name AS template_name
                 FROM documents d JOIN template_versions v ON v.id=d.template_version_id
                 JOIN templates t ON t.id=v.template_id"""
        conditions = []
        params: list[Any] = []
        conditions.append("d.deleted_at IS NOT NULL" if include_deleted else "d.deleted_at IS NULL")
        if query.strip():
            conditions.append("(d.subject LIKE ? OR d.document_number LIKE ? OR d.document_date LIKE ? OR d.data_json LIKE ? OR t.name LIKE ?)")
            params.extend([f"%{query.strip()}%"] * 5)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY d.updated_at DESC"
        with self.connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("""SELECT d.*,t.name AS template_name FROM documents d
                                JOIN template_versions v ON v.id=d.template_version_id
                                JOIN templates t ON t.id=v.template_id WHERE d.id=?""", (document_id,)).fetchone()
        return {**dict(row), "data": json.loads(row["data_json"])} if row else None

    def save_document(self, data: dict[str, Any], *, document_id: str | None = None, template_version_id: str | None = None) -> dict[str, Any]:
        template_id = str(data.get("template_id") or "")
        current = self.current_template(template_id)
        if not current:
            raise ValueError("กรุณาเลือกแม่แบบ")
        timestamp = now()
        if document_id:
            previous = self.get_document(document_id)
            if not previous or previous["deleted_at"]:
                raise KeyError("ไม่พบเอกสาร")
            version_id = previous["template_version_id"]
        else:
            document_id = str(uuid.uuid4())
            version_id = template_version_id or current["id"]
        subject = str(data.get("subject") or "").strip() or "ยังไม่ระบุเรื่อง"
        with self.connect() as db:
            if self.get_document(document_id):
                db.execute(
                    """UPDATE documents SET subject=?,document_number=?,document_date=?,status=?,data_json=?,updated_at=? WHERE id=?""",
                    (subject, str(data.get("document_number") or ""), str(data.get("date") or ""), "draft", json.dumps(data, ensure_ascii=False), timestamp, document_id),
                )
            else:
                db.execute(
                    "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,NULL)",
                    (document_id, version_id, subject, str(data.get("document_number") or ""), str(data.get("date") or ""), "draft", json.dumps(data, ensure_ascii=False), timestamp, timestamp),
                )
        self._remember_vendors(data)
        return self.get_document(document_id)  # type: ignore[return-value]

    def _remember_vendors(self, data: dict[str, Any]) -> None:
        names = {str(quote.get("company") or "").strip() for item in data.get("items", []) for quote in item.get("quotes", [])}
        with self.connect() as db:
            for name in names:
                if not name:
                    continue
                normalized = normalize_vendor(name)
                db.execute(
                    """INSERT INTO vendors(id,name,normalized,usage_count,updated_at) VALUES(?,?,?,?,?)
                       ON CONFLICT(normalized) DO UPDATE SET usage_count=usage_count+1,updated_at=excluded.updated_at""",
                    (str(uuid.uuid4()), name, normalized, 1, now()),
                )

    def search_vendors(self, query: str) -> list[dict[str, Any]]:
        normalized = normalize_vendor(query)
        with self.connect() as db:
            rows = db.execute("SELECT name,normalized,usage_count FROM vendors").fetchall()
        def score(row) -> tuple[int, float, int]:
            name = row["normalized"]
            if name == normalized:
                return (0, 0, -row["usage_count"])
            if name.startswith(normalized):
                return (1, 0, -row["usage_count"])
            if normalized in name:
                return (2, 0, -row["usage_count"])
            return (3, -SequenceMatcher(None, normalized, name).ratio(), -row["usage_count"])
        matches = [row for row in rows if not normalized or normalized in row["normalized"] or row["normalized"] in normalized or SequenceMatcher(None, normalized, row["normalized"]).ratio() >= 0.62]
        matches.sort(key=score)
        return [dict(row) for row in matches[:10]]

    def duplicate_document(self, document_id: str) -> dict[str, Any]:
        existing = self.get_document(document_id)
        if not existing:
            raise KeyError("ไม่พบเอกสาร")
        data = existing["data"].copy()
        data["subject"] = data.get("subject", "") + " (สำเนา)"
        data["document_number"] = ""
        return self.save_document(data, template_version_id=existing["template_version_id"])

    def set_deleted(self, document_id: str, deleted: bool) -> None:
        with self.connect() as db:
            result = db.execute(
                "UPDATE documents SET deleted_at=?,updated_at=? WHERE id=?",
                (None if not deleted else now(), now(), document_id),
            )
            if result.rowcount != 1:
                raise KeyError("ไม่พบเอกสาร")


def normalize_vendor(value: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in value if ch.isalnum())
