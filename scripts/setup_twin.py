"""
Create (or rebuild) the Warehouse Digital Twin schema in PostgreSQL.

    python scripts/setup_twin.py           # create + seed if missing (safe to repeat)
    python scripts/setup_twin.py --reset   # drop the twin schema and reload the demo data

Uses TWIN_DATABASE_URL, or DATABASE_URL when that is PostgreSQL.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.twin import ensure_twin_schema, is_enabled  # noqa: E402
from database.twin.connection import twin_schema  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop and rebuild the twin schema (deletes twin data)")
    parser.add_argument("--no-seed", action="store_true", help="create tables without the demo warehouse")
    args = parser.parse_args()

    if not is_enabled():
        print("The digital twin needs PostgreSQL. Set TWIN_DATABASE_URL (or a postgresql DATABASE_URL).")
        return 1
    created = ensure_twin_schema(seed=not args.no_seed, reset=args.reset)
    print(f"Twin schema '{twin_schema()}' {'created' if created else 'already present'}; realtime triggers installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
