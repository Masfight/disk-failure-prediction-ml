import json
import subprocess
import datetime as dt
from pathlib import Path


def run_cmd(cmd, timeout_sec=30):
    """
    Запуск команды с захватом stdout/stderr.
    Возвращает subprocess.CompletedProcess
    """
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
    HDD = rotational disk (rota=1), type=disk, исключаем tran=usb.

    Возвращает список словарей:
      {
        "path": "/dev/sdc",
        "model": "ST9640423AS",
        "serial": "5WS2BE1J",
        "tran": "sata",
        "size_bytes": 640135028736
      }
    """
    cp = run_cmd(["lsblk", "-J", "-O", "-b", "-p"], timeout_sec=20)
    if cp.returncode != 0 or not (cp.stdout and cp.stdout.strip()):
        raise RuntimeError("lsblk failed rc=%s: %s" % (cp.returncode, (cp.stderr or "").strip()))

    try:
        data = json.loads(cp.stdout)
    except Exception as e:
        raise RuntimeError("lsblk JSON parse failed: %s" % str(e))

    out = []

    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue

        rota = dev.get("rota")
        try:
            rota_int = int(rota)
        except Exception:
            continue
        if rota_int != 1:
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
    out_dir: str|Path (папка куда складываем логи)
    Возвращает Path к файлу лога.
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