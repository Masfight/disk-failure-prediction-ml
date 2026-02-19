import argparse
import sys
from pathlib import Path

from app.smartctl_collect import list_hdd_devices_excluding_usb, dump_smartctl_a


def cmd_detect(args):
    try:
        hdds = list_hdd_devices_excluding_usb()
    except Exception as e:
        print("ERROR: failed to detect HDD devices: %s" % str(e), file=sys.stderr)
        return 2

    if not hdds:
        print("No HDD devices found (excluding USB).")
        return 0

    print("Detected HDD devices (excluding USB):")
    for d in hdds:
        path = d.get("path") or "NA"
        model = d.get("model") or "NA"
        serial = d.get("serial") or "NA"
        tran = d.get("tran") or "NA"
        size_b = d.get("size_bytes") or "NA"

        print("  - %s  model=%s  serial=%s  tran=%s  size_bytes=%s" %
              (path, model, serial, tran, size_b))

    return 0

def cmd_collect(args):
    # куда складываем логи (по умолчанию ./smartctl_logs)
    logs_dir = Path(args.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    try:
        hdds = list_hdd_devices_excluding_usb()
    except Exception as e:
        print("ERROR: failed to detect HDD devices: %s" % str(e), file=sys.stderr)
        return 2

    if not hdds:
        print("No HDD devices found (excluding USB).")
        return 0

    targets = hdds

    if args.device:
        targets = []
        for d in hdds:
            if d.get("path") == args.device:
                targets.append(d)
        if not targets:
            print("ERROR: device not found among detected HDD: %s" % args.device, file=sys.stderr)
            return 2

    if args.all:
        pass
    else:
        # если не указан --all, берём только первый (или выбранный --device)
        targets = [targets[0]]

    for d in targets:
        dev = d.get("path")
        if not dev:
            continue

        try:
            log_path = dump_smartctl_a(dev, out_dir=logs_dir, timeout_sec=int(args.timeout))
        except Exception as e:
            print("ERROR: smartctl failed for %s: %s" % (dev, str(e)), file=sys.stderr)
            return 2

        print("Saved log: %s" % str(log_path))

    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="disk-tool",
        description="Tool for HDD SMART collection and ML-based failure risk prediction"
    )

    subparsers = parser.add_subparsers(dest="command",title="commands",metavar="")

    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect HDD devices (excluding USB)"
    )
    detect_parser.set_defaults(func=cmd_detect)

    collect_parser = subparsers.add_parser(
        "collect",
        help="Collect SMART data using smartctl and save logs"
    )
    collect_parser.add_argument("--device", default=None, help="Device path like /dev/sdc")
    collect_parser.add_argument("--all", action="store_true", help="Collect logs for all detected HDD")
    collect_parser.add_argument("--logs-dir", default="smartctl_logs", help="Directory for smartctl logs")
    collect_parser.add_argument("--timeout", default="60", help="smartctl timeout in seconds")
    collect_parser.set_defaults(func=cmd_collect)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())