#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import re
import sys
import datetime as dt
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


# Набор атрибутов
SMART_IDS = [
    1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 15, 22,
    183, 184, 187, 188, 189, 190, 191, 192, 193, 194,
    195, 196, 197, 198, 199, 200, 201, 220, 222, 223,
    224, 225, 226, 240, 241, 242, 250, 251, 252, 254, 255
]


def run_cmd(cmd, timeout_sec=30):
    """Запуск команды с захватом stdout/stderr."""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_sec,
        check=False,
    )


def list_hdd_devices_excluding_usb():
    """
    HDD = rotational disk (rota=1), type=disk, исключаем tran=usb
    Возвращает список dict: {path, model, serial, tran, size_bytes}
    """
    cp = run_cmd(["lsblk", "-J", "-O", "-b", "-p"], timeout_sec=20)
    if cp.returncode != 0 or not cp.stdout.strip():
        raise RuntimeError("lsblk failed rc=%s: %s" % (cp.returncode, cp.stderr.strip()))

    data = json.loads(cp.stdout)
    out = []

    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue

        rota = dev.get("rota")
        try:
            rota = int(rota)
        except Exception:
            continue
        if rota != 1:
            continue

        tran = (dev.get("tran") or "").lower()
        if tran == "usb":
            continue

        path = dev.get("name")
        if not path:
            continue

        out.append({
            "path": path,
            "model": dev.get("model"),
            "serial": dev.get("serial"),
            "tran": tran,
            "size_bytes": dev.get("size"),
        })

    return out


def dump_smartctl_a(device, out_dir, timeout_sec=60):
    """
    Выполняет `smartctl -a <device>` и пишет stdout+stderr в лог.
    out_dir: Path
    Возвращает Path к логу.
    """
    if not isinstance(out_dir, Path):
        out_dir = Path(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dev_safe = device.replace("/", "_")
    log_path = out_dir / ("smartctl-a%s_%s.log" % (dev_safe, ts))

    cp = run_cmd(["smartctl", "-a", device], timeout_sec=timeout_sec)

    with open(str(log_path), "w", encoding="utf-8") as f:
        f.write("# timestamp: %s\n" % dt.datetime.now().isoformat())
        f.write("# cmd: smartctl -a %s\n" % device)
        f.write("# returncode: %s\n\n" % cp.returncode)
        if cp.stdout:
            f.write(cp.stdout)
        if cp.stderr:
            f.write("\n\n# --- STDERR ---\n")
            f.write(cp.stderr)

    return log_path


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
    Парсит таблицу smartctl, где RAW_VALUE может содержать пробелы/скобки.
    """
    attrs = {}
    in_table = False

    for line in text.splitlines():
        if line.startswith("ID# ATTRIBUTE_NAME"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.strip():
            continue

        # ожидаем строки, начинающиеся с числа (ID)
        if not re.match(r"^\s*\d+\s+", line):
            continue

        # Разрезаем на 10 полей максимум:
        # ID, NAME, FLAG, VALUE, WORST, THRESH, TYPE, UPDATED, WHEN_FAILED, RAW_VALUE(rest)
        parts = line.split(None, 9)
        if len(parts) < 10:
            continue

        try:
            attr_id = int(parts[0])
            value = int(parts[3])  # VALUE (normalized)
            raw_field = parts[9]   # RAW_VALUE целиком
        except Exception:
            continue

        m = re.search(r"-?\d+", raw_field)
        if m:
            raw_val = int(m.group(0))
        else:
            raw_val = raw_field

        attrs[attr_id] = {"normalized": value, "raw": raw_val}

    return attrs


def build_backblaze_row(log_path, failure=0):
    if not isinstance(log_path, Path):
        log_path = Path(log_path)

    text = log_path.read_text(encoding="utf-8", errors="replace")

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


def main():
    logs_dir = Path.cwd() / "smartctl_logs"
    out_csv = Path.cwd() / ("smartctl_backblaze_%s.csv" % dt.date.today().isoformat())

    try:
        hdds = list_hdd_devices_excluding_usb()
    except Exception as e:
        print("ERROR: не смог получить список дисков: %s" % e, file=sys.stderr)
        return 2

    if not hdds:
        print("HDD (не USB) не найдены.")
        return 0

    print("Найдены HDD (USB исключены):")
    for d in hdds:
        print("  - %s  model=%s serial=%s tran=%s" % (
            d.get("path"),
            d.get("model"),
            d.get("serial"),
            d.get("tran"),
        ))

    rows = []

    for d in hdds:
        dev = d["path"]
        log_path = dump_smartctl_a(dev, out_dir=logs_dir, timeout_sec=60)
        print("Лог сохранён: %s" % log_path)

        row = build_backblaze_row(log_path, failure=0)
        rows.append(row)

    write_csv(rows, out_csv)
    print("\nCSV сохранён: %s" % out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
