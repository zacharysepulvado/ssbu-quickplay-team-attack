#!/usr/bin/env python3
"""Review passive 0.2.6 B4 caller/local/selected-slot observations."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


KINDS = ["local_copy", "participant_copy", "selection_ready", "apply_before",
         "apply_after", "rule_submit", "rule_receive_before",
         "rule_receive_team_stored"]
ORIGINS = {"state_update", "local_record", "per_slot", "initial_local", "unknown"}


def review(path):
    raw = path.read_bytes()
    lines = raw.decode("utf-8-sig").splitlines()
    headers = {}
    for line in lines:
        match = re.fullmatch(r"# (\w+)=(.*)", line)
        if match:
            key, value = match.groups()
            if key in headers:
                raise ValueError("Duplicate header: " + key)
            headers[key] = value
    if (headers.get("observer_version"), headers.get("game_version"),
            headers.get("run_label")) != ("0.2.6", "13.0.5", "RULE_OWNER_BATCH_01"):
        raise ValueError("Expected observer 0.2.6 / SSBU 13.0.5 / RULE_OWNER_BATCH_01")

    prefix = "# application_event: "
    events = [dict(item.split(":", 1) for item in line[len(prefix):].split())
              for line in lines if line.startswith(prefix)]
    events.sort(key=lambda event: int(event["elapsed_ticks"]))
    required = {"kind", "participant_slot", "local_slot", "selected_owner_slot",
                "submit_origin", "elapsed_ticks"}
    if any(not required <= event.keys() for event in events):
        raise ValueError("Application event is missing a 0.2.6 owner field")
    if any(event["submit_origin"] not in ORIGINS for event in events):
        raise ValueError("Unknown submit-origin spelling")
    valid_slot = re.compile(r"(?:0[0-9A-F]|FF)\Z")
    if any(not all(valid_slot.fullmatch(event[key]) for key in
                   ("participant_slot", "local_slot", "selected_owner_slot"))
           for event in events):
        raise ValueError("Invalid bounded slot")

    counts = Counter(event["kind"] for event in events)
    submissions = [event for event in events if event["kind"] == "rule_submit"]
    selections = [event for event in events if event["kind"] in
                  ("local_copy", "participant_copy")]
    return {
        "file": path.name,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "headers": headers,
        "event_counts": dict(counts),
        "submit_origin_counts": dict(Counter(event["submit_origin"] for event in submissions)),
        "submit_local_slot_pairs": dict(Counter(
            event["local_slot"] + "/" + event["participant_slot"] for event in submissions)),
        "selection_local_owner_pairs": dict(Counter(
            event["local_slot"] + "/" + event["selected_owner_slot"] for event in selections)),
        "submissions": submissions,
        "selections": selections,
        "scope": "Bounded session-slot and caller classifications only; not account IDs, formal host authority, server acceptance, peer agreement, completion markers, or ban safety.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps({"format": "SSBU_RULE_OWNER_026_REVIEW_1",
                      "captures": [review(path) for path in args.logs]}, indent=2))
