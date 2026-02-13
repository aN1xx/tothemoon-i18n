import argparse
import json
import sys
from pathlib import Path

from tools.validators import check_intent_style, check_keys, check_tokens


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a JSON object at the root")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify i18n translation integrity")
    parser.add_argument("--src", default="data/TTM_EN.json", help="Path to the source locale JSON")
    parser.add_argument(
        "--dst", default="data/TTM_RU.json", help="Path to the translated locale JSON"
    )
    args = parser.parse_args()

    src = load_json(Path(args.src))
    dst = load_json(Path(args.dst))

    ok = True
    if not check_keys(src, dst):
        ok = False
    if not check_tokens(src, dst):
        ok = False

    style_ok, messages = check_intent_style(src, dst)
    for msg in messages:
        print(msg)
    if not style_ok:
        ok = False

    if ok:
        print("[ok] lint passed")
        return 0
    print("[fail] lint failed")
    return 2


if __name__ == "__main__":
    sys.exit(main())
