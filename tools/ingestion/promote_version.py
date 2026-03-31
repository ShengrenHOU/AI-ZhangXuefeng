from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: py promote_version.py <reviewed_dir> <published_dir>")
        return 1

    reviewed_dir = Path(sys.argv[1])
    published_dir = Path(sys.argv[2])
    if not reviewed_dir.exists():
        raise FileNotFoundError(reviewed_dir)
    published_dir.mkdir(parents=True, exist_ok=True)
    for file in reviewed_dir.glob("*.json"):
        shutil.copy2(file, published_dir / file.name)
    print(f"promoted {reviewed_dir} -> {published_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

