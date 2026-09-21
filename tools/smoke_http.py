"""End-to-end API smoke check against a running local server."""

import json
import sys
from urllib.request import Request, urlopen
from zipfile import ZipFile
from io import BytesIO


base = f"http://127.0.0.1:{int(sys.argv[1]) if len(sys.argv) > 1 else 8765}/api"


def call(path, method="GET", body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(base + path, data=data, method=method,
                      headers={"Content-Type": "application/json"} if data else {})
    with urlopen(request, timeout=120) as response:
        content = response.read()
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return json.loads(content)
        return content


templates = call("/templates")
template_id = templates[0]["id"]
form = {
    "template_id": template_id,
    "subject": "ราคากลางงานจัดซื้อวัสดุทดสอบระบบ",
    "document_number": "ทดลอง/69",
    "date": "2026-09-16",
    "items": [
        {"name": "ดินสอ", "quantity": "2", "unit": "กล่อง", "source": "prior",
         "prior": {"document_number": "100/68", "document_date": "2025-09-11", "quantity": "2", "unit_price": "100"},
         "quotes": [{"company": "ร้านทดสอบ ก", "unit_price": "100"}, {"company": "ร้านทดสอบ ข", "unit_price": "120"}]},
        {"name": "ปากกา", "quantity": "3", "unit": "ด้าม", "source": "reference",
         "reference": {"quantity": "3", "unit_price": "50"}, "quotes": []},
        {"name": "กระดาษ", "quantity": "4", "unit": "รีม", "source": "market",
         "quotes": [{"company": "ร้านทดสอบ ก", "unit_price": "70"}, {"company": "ร้านทดสอบ ข", "unit_price": "80"}]},
    ],
}
assert call("/documents/validate", "POST", form)["total"] == "630.00"
saved = call("/documents", "POST", form)
document_id = saved["id"]
assert call(f"/documents/{document_id}")["data"]["subject"] == form["subject"]
docx = call(f"/documents/{document_id}/export/docx")
pdf = call(f"/documents/{document_id}/export/pdf")
assert docx[:2] == b"PK" and pdf[:4] == b"%PDF"
with ZipFile(BytesIO(docx)) as archive:
    xml = archive.read("word/document.xml").decode("utf-8")
    assert "๖๓๐" in xml and "ดินสอ" in xml and "ปากกา" in xml
assert len(call("/vendors?q=" + "%E0%B8%97%E0%B8%94%E0%B8%AA%E0%B8%AD%E0%B8%9A")) >= 1
copy = call(f"/documents/{document_id}/duplicate", "POST", {})
assert copy["template_version_id"] == saved["template_version_id"]
call(f"/documents/{copy['id']}", "DELETE")
assert any(row["id"] == copy["id"] for row in call("/documents?trash=1"))
call(f"/documents/{copy['id']}/restore", "POST", {})
assert any(row["id"] == copy["id"] for row in call("/documents"))
backup = call("/backup")
assert ZipFile(BytesIO(backup)).testzip() is None
print(f"PASS: 3 item types, total 630.00, DOCX {len(docx)} bytes, PDF {len(pdf)} bytes, copy/trash/restore/backup")
