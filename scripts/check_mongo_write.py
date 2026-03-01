#!/usr/bin/env python3
"""Smoke-test MongoDB write/read without requiring pymongo.

This uses mongosh so it still works when pip/network constraints prevent
installing drivers in the current environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv


def main() -> int:
    # Force .env values to win over any shell-exported MONGODB_URI.
    load_dotenv(override=True)
    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI is not set in environment/.env", file=sys.stderr)
        return 1
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        print("ERROR: MONGODB_URI must start with mongodb:// or mongodb+srv://", file=sys.stderr)
        return 1

    parsed = urlparse(uri)
    print(f"using_host: {parsed.hostname or '<unknown>'}")

    ts = datetime.now(timezone.utc).isoformat()
    js = f"""
const adminDb = db.getSiblingDB("admin");
const appDb = db.getSiblingDB("dombot");
const doc = {{ ts: {json.dumps(ts)}, source: "primary-route-test" }};
const res = appDb.write_test.insertOne(doc);
const found = appDb.write_test.findOne({{ _id: res.insertedId }});
printjson({{
  ping: adminDb.runCommand({{ ping: 1 }}),
  inserted_id: res.insertedId,
  read_back: !!found
}});
"""
    try:
        subprocess.run(
            ["mongosh", "--norc", uri, "--quiet", "--eval", js],
            check=True,
        )
    except FileNotFoundError:
        print(
            "ERROR: mongosh is not installed. Install MongoDB Shell to use this checker.",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: mongosh write check failed (exit={exc.returncode})", file=sys.stderr)
        return exc.returncode or 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
