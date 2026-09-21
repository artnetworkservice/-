"""Deterministic pricing and Thai document numbering.

Prices enter and leave this module as decimal strings. No binary float arithmetic is
used for money. An item with a cheaper historical price than every quote remains
unresolved until the document owner chooses the required policy.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


SATANG = Decimal("0.01")
THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")
ARABIC_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


class ValidationError(ValueError):
    pass


def thai_number(value: Any) -> str:
    return str(value).translate(THAI_DIGITS)


def money(value: Any) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "").translate(ARABIC_DIGITS))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("กรุณาระบุราคาเป็นตัวเลข") from exc
    if not result.is_finite() or result < 0:
        raise ValidationError("ราคาต้องเป็นศูนย์หรือมากกว่า")
    if result != result.quantize(SATANG):
        raise ValidationError("ราคาใส่ทศนิยมได้ไม่เกิน 2 ตำแหน่ง")
    return result


def quantity(value: Any) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "").translate(ARABIC_DIGITS))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("กรุณาระบุจำนวนเป็นตัวเลข") from exc
    if not result.is_finite() or result <= 0:
        raise ValidationError("จำนวนต้องมากกว่าศูนย์")
    if result.as_tuple().exponent < -3:
        raise ValidationError("จำนวนใส่ทศนิยมได้ไม่เกิน 3 ตำแหน่ง")
    return result


def format_money(value: Decimal, *, thai: bool = True) -> str:
    result = f"{value:,.2f}"
    if result.endswith(".00"):
        result = result[:-3]
    return thai_number(result) if thai else result


def format_quantity(value: Decimal, *, thai: bool = True) -> str:
    result = f"{value.normalize():f}"
    return thai_number(result) if thai else result


def calculate_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    name = str(item.get("name") or "").strip()
    unit = str(item.get("unit") or "").strip()
    if not name:
        raise ValidationError(f"รายการที่ {index}: กรุณาระบุรายละเอียดพัสดุ")
    if not unit:
        raise ValidationError(f"รายการที่ {index}: กรุณาระบุหน่วย")
    qty = quantity(item.get("quantity", ""))
    source = item.get("source")
    if source not in ("reference", "market", "prior"):
        raise ValidationError(f"รายการที่ {index}: กรุณาเลือกแหล่งราคา")

    result: dict[str, Any] = {
        "index": index,
        "name": name,
        "unit": unit,
        "quantity": qty,
        "source": source,
        "quotes": [],
        "prior": None,
        "reference": None,
    }
    if source == "reference":
        reference = item.get("reference") or {}
        price = money(reference.get("unit_price", ""))
        ref_qty = quantity(reference.get("quantity", qty))
        if ref_qty != qty:
            raise ValidationError(f"รายการที่ {index}: จำนวนราคาอ้างอิงต้องตรงกับจำนวนรายการ")
        result["reference"] = {"unit_price": price, "quantity": ref_qty}
        result["selected_unit_price"] = price
        result["decision"] = "reference"
    else:
        quotes = item.get("quotes") or []
        if not isinstance(quotes, list) or not quotes:
            raise ValidationError(f"รายการที่ {index}: ต้องมีบริษัทที่เสนอราคาอย่างน้อย 1 ราย")
        names: set[str] = set()
        for quote in quotes:
            company = str(quote.get("company") or "").strip()
            if not company:
                raise ValidationError(f"รายการที่ {index}: กรุณาระบุชื่อบริษัท")
            key = "".join(company.split()).casefold()
            if key in names:
                raise ValidationError(f"รายการที่ {index}: ชื่อบริษัทซ้ำในรายการเดียวกัน")
            names.add(key)
            result["quotes"].append({"company": company, "unit_price": money(quote.get("unit_price", ""))})
        lowest = min(quote["unit_price"] for quote in result["quotes"])
        if source == "prior":
            prior = item.get("prior") or {}
            document_number = str(prior.get("document_number") or "").strip()
            if not document_number:
                raise ValidationError(f"รายการที่ {index}: กรุณาระบุเลขที่เอกสารซื้อครั้งก่อน")
            prior_price = money(prior.get("unit_price", ""))
            result["prior"] = {
                "document_number": document_number,
                "document_date": str(prior.get("document_date") or "").strip(),
                "quantity": str(prior.get("quantity") or "").strip(),
                "unit_price": prior_price,
            }
            if prior_price < lowest:
                raise ValidationError(
                    f"รายการที่ {index}: ราคาเคยซื้อ {format_money(prior_price, thai=False)} บาท "
                    f"ต่ำกว่าราคาเสนอทุกบริษัท ({format_money(lowest, thai=False)} บาท) "
                    "ต้องยืนยันกติกาเลือกราคากลางก่อนส่งออก"
                )
            result["decision"] = "equal" if prior_price == lowest else "market_lower"
        else:
            result["decision"] = "market_only"
        result["selected_unit_price"] = lowest
    result["total"] = (result["selected_unit_price"] * qty).quantize(SATANG, rounding=ROUND_HALF_UP)
    return result


def calculate_document(data: dict[str, Any]) -> dict[str, Any]:
    subject = str(data.get("subject") or "").strip()
    if not subject:
        raise ValidationError("กรุณาระบุเรื่อง")
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        raise ValidationError("กรุณาเพิ่มรายการจัดซื้ออย่างน้อย 1 รายการ")
    calculated = [calculate_item(item, i) for i, item in enumerate(items, 1)]
    return {
        "subject": subject,
        "document_number": str(data.get("document_number") or "").strip(),
        "date": str(data.get("date") or "").strip(),
        "items": calculated,
        "total": sum((item["total"] for item in calculated), Decimal("0.00")),
    }


THAI_ONES = ("", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า")
THAI_POSITIONS = ("", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน")


def _six_digit_words(number: int) -> str:
    digits = list(map(int, str(number).zfill(6)))
    result = ""
    for pos, digit in enumerate(digits):
        if not digit:
            continue
        place = 5 - pos
        if place == 1:
            result += "สิบ" if digit == 1 else "ยี่สิบ" if digit == 2 else THAI_ONES[digit] + "สิบ"
        elif place == 0:
            result += "เอ็ด" if digit == 1 and number > 1 else THAI_ONES[digit]
        else:
            result += THAI_ONES[digit] + THAI_POSITIONS[place]
    return result


def thai_baht_words(amount: Decimal) -> str:
    amount = amount.quantize(SATANG, rounding=ROUND_HALF_UP)
    baht = int(amount)
    satang = int((amount - baht) * 100)
    if baht == 0:
        result = "ศูนย์"
    else:
        groups = []
        while baht:
            groups.append(baht % 1_000_000)
            baht //= 1_000_000
        result = ""
        for i in range(len(groups) - 1, -1, -1):
            if groups[i]:
                result += _six_digit_words(groups[i])
            if i:
                result += "ล้าน"
    result += "บาท"
    return result + ("ถ้วน" if satang == 0 else _six_digit_words(satang) + "สตางค์")


def compact_item_references(numbers: list[int], *, suffix: str = "") -> str:
    """Render consecutive item IDs as ๒.๑ - ๒.๓, keeping suffixes on both ends."""
    if not numbers:
        return ""
    ordered = sorted(set(numbers))
    ranges = []
    start = end = ordered[0]
    for number in ordered[1:]:
        if number == end + 1:
            end = number
        else:
            ranges.append((start, end))
            start = end = number
    ranges.append((start, end))
    def ref(number: int) -> str:
        return thai_number(f"2.{number}{suffix}")
    return " , ".join(ref(a) if a == b else f"{ref(a)} - {ref(b)}" for a, b in ranges)
