#!/usr/bin/env python3
"""Summarize online doubles rule selection without a high-frequency game hook.

This reads the bounded application events already emitted by alpha.6 or later.
An application event is a rule selection, not proof that a match completed or
that every console applied the same setting.
"""
import argparse
from collections import Counter
from pathlib import Path


def events(path):
    for line in path.read_text(errors="replace").splitlines():
        if "application_event:" not in line:
            continue
        fields = dict(
            field.split(":", 1)
            for field in line.split("application_event:", 1)[1].split()
            if ":" in field
        )
        if fields.get("mode") == "07010102" and fields.get("request") == "2":
            yield fields


def selections(path):
    stream = sorted(events(path), key=lambda e: int(e["elapsed_ticks"]))
    previous_tick = -1
    for selected in (e for e in stream if e["kind"] == "apply_after"):
        tick = int(selected["elapsed_ticks"])
        window = [e for e in stream if previous_tick < int(e["elapsed_ticks"]) <= tick]
        copies = [e for e in window if e["kind"] in ("local_copy", "participant_copy")]
        copy = copies[-1] if copies else None
        owner = "local" if copy and copy["kind"] == "local_copy" else (
            "participant" if copy else "unknown"
        )
        slot = copy["participant_slot"] if copy and owner == "participant" else None
        received = [
            e for e in window
            if e["kind"] == "rule_receive_before"
            and (slot is None or e["participant_slot"] == slot)
        ]
        first_off = next((e for e in received if e["rule_team"] == "00"), None)
        later_on = next(
            (e for e in received if first_off and int(e["elapsed_ticks"]) > int(first_off["elapsed_ticks"])
             and e["rule_team"] == "01"), None
        )
        proposals = [e for e in window if e["kind"] == "rule_submit" and e["rule_team"] == "01"]
        yield {
            "time": selected["elapsed_ms"], "team": selected["rule_team"],
            "owner": owner, "slot": slot, "fingerprint": selected.get("rule_fp", "unknown"),
            "off_to_on": bool(first_off and later_on), "on_proposals": len(proposals),
            "off_first_ms": first_off["elapsed_ms"] if first_off else None,
            "on_later_ms": later_on["elapsed_ms"] if later_on else None,
        }
        previous_tick = tick


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", type=Path, nargs="+")
    args = parser.parse_args()
    for path in args.logs:
        rows = list(selections(path))
        print(f"{path}: {len(rows)} selected rules")
        for number, row in enumerate(rows, 1):
            seconds = int(row["time"]) // 1000
            transition = "OFF->ON" if row["off_to_on"] else "no observed OFF->ON"
            print(f"  {number:2} {seconds//60:02}:{seconds%60:02} "
                  f"{row['owner']:11} TA={row['team']} slot={row['slot'] or '-'} "
                  f"ON_submits={row['on_proposals']} {transition} fp={row['fingerprint']}")
        print("  totals:", dict(sorted(Counter((r["owner"], r["team"]) for r in rows).items())))


if __name__ == "__main__":
    main()
