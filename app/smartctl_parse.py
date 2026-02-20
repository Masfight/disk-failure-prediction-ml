#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import re
import datetime as dt
from pathlib import Path


# Набор атрибутов
SMART_IDS = [
    1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 15, 22,
    183, 184, 187, 188, 189, 190, 191, 192, 193, 194,
    195, 196, 197, 198, 199, 200, 201, 220, 222, 223,
    224, 225, 226, 240, 241, 242, 250, 251, 252, 254, 255
]


def parse_capacity_bytes(text):
    # User Capacity:    640 135 028 736 bytes [640 GB]
    m = re.search(r"^User Capacity:\s*([\d\s\u202f\u00a0]+)\s*bytes", text, flags=re.MULTILINE)
    if not m:
        return None
    s = m.group(1)
    s = s.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    try:
        return int(s)
    except Exception:
        return None


def parse_model_serial(text):
    model = None
    serial = None

    m = re.search(r"^Device Model:\s*(.+)$", text, flags=re.MULTILINE)
    if m:
        model = m.group(1).strip()
    else:
        m = re.search(r"^Model Number:\s*(.+)$", text, flags=re.MULTILINE)
        if m:
            model = m.group(1).strip()

    m = re.search(r"^Serial Number:\s*(.+)$", text, flags=re.MULTILINE)
    if m:
        serial = m.group(1).strip()

    return model, serial


def parse_smart_attributes(text):
    """
    Возвращает:
      { id: {"normalized": int, "raw": int|str} }

    Парсит таблицу smartctl:
    ID# ATTRIBUTE_NAME FLAG VALUE WORST THRESH TYPE UPDATED WHEN_FAILED RAW_VALUE

    RAW_VALUE может быть вида:
      "28 (Min/Max 27/30)" -> берём первое число (28)
    """
    attrs = {}

    line_re = re.compile(
        r"^\s*(\d{1,3})\s+([A-Za-z0-9_\-]+)\s+0x[0-9A-Fa-f]{4}\s+"
        r"(\d+)\s+(\d+)\s+(\d+)\s+.+?\s+(\S+)\s*$"
    )

    for line in text.splitlines():
        mm = line_re.match(line)
        if not mm:
            continue

        try:
            attr_id = int(mm.group(1))
            value = int(mm.group(3))      # normalized VALUE
            raw_str = mm.group(6)         # последняя колонка RAW_VALUE
        except Exception:
            continue

        raw_val = raw_str
        mraw = re.search(r"-?\d+", raw_str)
        if mraw:
            try:
                raw_val = int(mraw.group(0))
            except Exception:
                raw_val = raw_str

        attrs[attr_id] = {"normalized": value, "raw": raw_val}

    return attrs


def build_backblaze_row_from_text(text, failure=0, date_str=None):
    if date_str is None:
        date_str = dt.date.today().isoformat()

    model, serial = parse_model_serial(text)
    cap = parse_capacity_bytes(text)
    attrs = parse_smart_attributes(text)

    row = {
        "date": date_str,
        "serial_number": serial if serial else "NA",
        "model": model if model else "NA",
        "capacity_bytes": cap if cap is not None else "NA",
        "failure": int(failure),
    }

    for sid in SMART_IDS:
        norm_key = "smart_%d_normalized" % sid
        raw_key = "smart_%d_raw" % sid

        if sid in attrs:
            row[norm_key] = attrs[sid].get("normalized", "NA")
            row[raw_key] = attrs[sid].get("raw", "NA")
        else:
            row[norm_key] = "NA"
            row[raw_key] = "NA"

    return row


def build_backblaze_row(log_path, failure=0):
    if not isinstance(log_path, Path):
        log_path = Path(log_path)

    text = log_path.read_text(encoding="utf-8", errors="replace")
    return build_backblaze_row_from_text(text, failure=failure)


def write_csv(rows, out_csv):
    if not isinstance(out_csv, Path):
        out_csv = Path(out_csv)

    fieldnames = ["date", "serial_number", "model", "capacity_bytes", "failure"]
    for sid in SMART_IDS:
        fieldnames.append("smart_%d_normalized" % sid)
        fieldnames.append("smart_%d_raw" % sid)

    out_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(str(out_csv), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            w.writerow(r)