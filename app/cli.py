import argparse
import sys
from pathlib import Path
import joblib

from app.smartctl_collect import list_hdd_devices_excluding_usb, dump_smartctl_a
from app.smartctl_parse import build_backblaze_row, write_csv
from app.predictor import predict_from_csv

#DETECT
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

#COLLECT
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

#PARSE
def cmd_parse(args):
    log_path = Path(args.log)
    if not log_path.exists():
        print("ERROR: log file not found: %s" % str(log_path), file=sys.stderr)
        return 2

    out_csv = Path(args.out_csv)

    try:
        row = build_backblaze_row(log_path, failure=0)
        write_csv([row], out_csv)
    except Exception as e:
        print("ERROR: failed to parse log: %s" % str(e), file=sys.stderr)
        return 2

    print("CSV saved: %s" % str(out_csv))
    return 0

#PREDICT
def cmd_predict_csv(args):
    model_path = args.model
    csv_path = args.csv

    try:
        pipeline = joblib.load(model_path)
    except Exception as e:
        print("ERROR: failed to load model: %s" % str(e), file=sys.stderr)
        return 2

    try:
        df, pred, proba = predict_from_csv(pipeline, csv_path)
    except Exception as e:
        print("ERROR: prediction failed: %s" % str(e), file=sys.stderr)
        return 2

    # печать результатов по строкам
    for i in range(len(pred)):
        serial = "NA"
        model_name = "NA"

        if "serial_number" in df.columns:
            try:
                serial = str(df.loc[i, "serial_number"])
            except Exception:
                pass

        if "model" in df.columns:
            try:
                model_name = str(df.loc[i, "model"])
            except Exception:
                pass

        p = proba[i]

        print("Result #%d: serial=%s model=%s" % (i + 1, serial, model_name))
        print("  predicted_class: %s" % str(pred[i]))
        print("  probabilities: low=%.4f medium=%.4f high=%.4f" % (p[0], p[1], p[2]))

    return 0

def build_parser():
    parser = argparse.ArgumentParser(
        prog="disk-tool",
        description="Tool for HDD SMART collection and ML-based failure risk prediction"
    )

    subparsers = parser.add_subparsers(dest="command",title="commands",metavar="")

    #detect subcommand
    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect HDD devices (excluding USB)"
    )
    detect_parser.set_defaults(func=cmd_detect)

    #collect subcommand
    collect_parser = subparsers.add_parser(
        "collect",
        help="Collect SMART data using smartctl and save logs"
    )
    collect_parser.add_argument("--device", default=None, help="Device path like /dev/sdc")
    collect_parser.add_argument("--all", action="store_true", help="Collect logs for all detected HDD")
    collect_parser.add_argument("--logs-dir", default="smartctl_logs", help="Directory for smartctl logs")
    collect_parser.add_argument("--timeout", default="60", help="smartctl timeout in seconds")
    collect_parser.set_defaults(func=cmd_collect)

    #parse subcommand
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse smartctl log into CSV"
    )
    parse_parser.add_argument("--log", required=True, help="Path to smartctl log file")
    parse_parser.add_argument(
        "--out-csv",
        default="data/datasets/smartctl_parsed.csv",
        help="Output CSV path"
    )
    parse_parser.set_defaults(func=cmd_parse)

    #predict subcommand
    predict_csv_parser = subparsers.add_parser(
        "predict",
        help="Predict risk class from CSV"
    )
    predict_csv_parser.add_argument(
        "--csv",
        required=True,
        help="Input CSV file (data/datasets/smartctl_local.csv)"
    )
    predict_csv_parser.add_argument(
        "--model",
        default="models/random_forest_hdd.joblib",
        help="Path to trained model (.joblib)"
    )
    predict_csv_parser.set_defaults(func=cmd_predict_csv)


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