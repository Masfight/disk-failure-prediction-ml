import json
import subprocess


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