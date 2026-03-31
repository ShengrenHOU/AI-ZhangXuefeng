from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: py normalize_sources.py <input.json> <output.json>")
        return 1

    source_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    data = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("input must be a JSON array")

    normalized = []
    for item in data:
        normalized.append({k.lower(): v for k, v in item.items()})

    output_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(normalized)} records to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

