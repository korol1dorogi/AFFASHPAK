"""CLI: python -m apps.demo_data --seed 42 --as-of 2026-10-01 --out /tmp/demo_data.json

Not a manage.py command yet: registering the app in INSTALLED_APPS is the lead's call.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from apps.demo_data.build import (
    DEFAULT_AS_OF,
    DEFAULT_COMPANY_COUNT,
    DEFAULT_SEED,
    build_dataset,
    dumps,
    sha256,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic demo data (S2, «демо»).")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF)
    parser.add_argument("--companies", type=int, default=DEFAULT_COMPANY_COUNT)
    parser.add_argument("--out", type=Path, help="Output file; stdout if omitted.")
    args = parser.parse_args(argv)

    data = dumps(build_dataset(args.seed, as_of=args.as_of, company_count=args.companies))
    if args.out is None:
        sys.stdout.buffer.write(data)
    else:
        args.out.write_bytes(data)
        sys.stderr.write(f"{args.out}: {len(data)} bytes, sha256 {sha256(data)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
