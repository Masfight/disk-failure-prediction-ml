import argparse
import sys

from app.smartctl_collect import list_hdd_devices_excluding_usb


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