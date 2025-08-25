# tools/sjr_to_json.py
import csv, json, sys, re

if len(sys.argv) < 3:
    print("Usage: python tools/sjr_to_json.py <input.csv> <output.json>")
    sys.exit(1)

inp, outp = sys.argv[1], sys.argv[2]

def norm_title(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

TITLE_HEADERS = {"title", "source title", "journal title"}
QUARTILE_HEADERS = {"sjr best quartile", "best quartile", "quartile"}

mapping = {}
with open(inp, newline="", encoding="utf-8", errors="ignore") as f:
    reader = csv.reader(f)
    rows = list(reader)
    if not rows:
        raise SystemExit("Empty CSV")

    header = [h.strip().lower() for h in rows[0]]
    try:
        t_idx = next(i for i,h in enumerate(header) if h in TITLE_HEADERS)
        q_idx = next(i for i,h in enumerate(header) if h in QUARTILE_HEADERS)
    except StopIteration:
        raise SystemExit(f"Could not find Title/Quartile columns in header: {header}")

    for r in rows[1:]:
        if not r or len(r) <= max(t_idx, q_idx):
            continue
        t = r[t_idx].strip()
        q = (r[q_idx] or "").strip().upper()
        if t and q in {"Q1","Q2","Q3","Q4"}:
            mapping[norm_title(t)] = q

with open(outp, "w", encoding="utf-8") as w:
    json.dump(dict(sorted(mapping.items())), w, ensure_ascii=False, indent=2)

print(f"Wrote {len(mapping):,} journal→quartile entries to {outp}")
