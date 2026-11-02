#!/usr/bin/env python3
"""Payment reconciliation.

Reads payments.jsonl and works out how much money we actually collected.
Run:  python3 reconcile.py
"""
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_ts(value):
    """Return a timezone-aware UTC datetime, or None if unparseable."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            v = float(value)
            if v > 1e11:          # milliseconds
                v /= 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        s = str(value).strip()
        if not s:
            return None
        if s.replace(".", "", 1).isdigit():   # numeric string epoch
            return parse_ts(float(s))
        if s.endswith(("Z", "z")):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def parse_amount(value):
    if isinstance(value, bool) or value is None:
        return Decimal(0)
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return Decimal(0)


MIN_TS = datetime.min.replace(tzinfo=timezone.utc)

latest = {}  # txn_id -> (ts, line_number, event)

with open("payments.jsonl", encoding="utf-8") as f:
    for n, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue

        txn_id = event.get("txn_id")
        if txn_id is None:
            continue
        txn_id = str(txn_id).strip()
        if not txn_id:
            continue

        ts = parse_ts(event.get("ts")) or MIN_TS
        key = (ts, n)  # ties on ts: later line wins
        prev = latest.get(txn_id)
        if prev is None or key >= (prev[0], prev[1]):
            latest[txn_id] = (ts, n, event)

total = Decimal(0)
count = 0
statuses = Counter()

for ts, n, event in latest.values():
    status = str(event.get("status", "")).strip().lower()
    statuses[status] += 1
    if status == "success":
        total += parse_amount(event.get("amount"))
        count += 1

with open("expected.txt") as f:
    expected = int(f.read().strip())

if count != expected:
    print(f"Check failed: counted {count} successful payments, expected {expected}.")
    print("Something in the data isn't being handled the way the README describes.")
    print(f"(debug) latest-attempt statuses: {dict(statuses)}")
else:
    print(f"Check passed: {count} successful payments.")
    print(f"Your code: KOYA-{int(total.quantize(Decimal('1'), rounding=ROUND_HALF_UP))}")