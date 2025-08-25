import json, time, sys, urllib.parse, urllib.request

# ================== CONFIG (edit these) ==================
ROR = "04q2jes40"  # <-- put your institution ROR *code* here (example shown). Not the full URL.
CONTACT = "surajrawat.2u94@gmail.com"  # <-- your personal email (for polite API identification)
FROM = "2010-01-01"
TO = f"{time.gmtime().tm_year}-12-31"
PER_PAGE = 50        # conservative page size to avoid throttling
PAGES_MAX = 200      # safety cap
# =========================================================

BASE = "https://api.openalex.org/works"
UA = f"Institution Sync (+mailto:{CONTACT})"

def get_page(cursor, per_page):
    params = {
        "per-page": str(per_page),
        "cursor": cursor,
        "mailto": CONTACT,
        "filter": f"institutions.ror:{ROR},from_publication_date:{FROM},to_publication_date:{TO}",
        "select": "id,doi,title,authorships,host_venue,publication_year,type,cited_by_count,primary_location,is_retracted",
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    # redact email in logs
    print("GET", url.replace(urllib.parse.quote(CONTACT), "hidden%40example.org"), flush=True)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "From": CONTACT,
            "Accept": "application/json",
            "Connection": "close",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            if resp.status != 200:
                # Return status + Retry-After (if present)
                retry_after = int(resp.headers.get("Retry-After", "0") or 0)
                return resp.status, None, None, retry_after
    except urllib.error.HTTPError as e:
        retry_after = int(e.headers.get("Retry-After", "0") or 0)
        return e.code, None, None, retry_after

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        print("Invalid JSON:", e, file=sys.stderr)
        sys.exit(1)

    items = []
    for w in data.get("results", []):
        doi = (w.get("doi") or "").replace("https://doi.org/", "").replace("http://doi.org/", "")
        host = w.get("host_venue") or {}
        issn_field = host.get("issn") or []
        if isinstance(issn_field, str):
            issn_list = [issn_field.upper()]
        else:
            issn_list = [str(x).upper() for x in issn_field]
        authors = []
        for a in (w.get("authorships") or []):
            au = a.get("author") or {}
            name = au.get("display_name")
            if name:
                authors.append(name)
        items.append({
            "doi": doi,
            "title": w.get("title") or "",
            "year": w.get("publication_year"),
            "type": w.get("type") or "",
            "citations": w.get("cited_by_count") or 0,
            "authors": authors,
            "journal": host.get("display_name") or "",
            "issns": issn_list,
            "url": (w.get("primary_location") or {}).get("landing_page_url") or (f"https://doi.org/{doi}" if doi else ""),
            "is_retracted": bool(w.get("is_retracted")),
        })
    next_cursor = (data.get("meta") or {}).get("next_cursor")
    return 200, items, next_cursor, 0

def polite_wait(ms):
    ms = min(ms, 120000)  # cap at 120s
    print(f"Waiting {ms}ms before retry…", flush=True)
    time.sleep(ms / 1000.0)

cursor = "*"
page = 0
all_items = []

# If first page gets 403 repeatedly, automatically try smaller per-page (25)
tried_smaller = False

while cursor and page < PAGES_MAX:
    page += 1
    print(f"\nFetching page {page}…", flush=True)
    status, items, next_cursor, retry_after = get_page(cursor, PER_PAGE)
    if status in (403, 429):
        backoff = (retry_after * 1000) if retry_after else (800 * (2 ** max(0, page - 1)))
        print(f"HTTP {status}.", flush=True)
        polite_wait(backoff)
        # If still on page 1 and we haven't tried smaller pages, switch to 25
        if page == 1 and not tried_smaller:
            print("Switching PER_PAGE from 50 to 25 and retrying page 1…", flush=True)
            tried_smaller = True
            page -= 1
            PER_PAGE = 25
            continue
        page -= 1
        continue
    if status != 200:
        print(f"HTTP {status}. Aborting.", file=sys.stderr)
        sys.exit(1)

    print(f"→ got {len(items)} items", flush=True)
    all_items.extend(items)
    if not items:
        break
    cursor = next_cursor
    time.sleep(0.3)  # small politeness delay

out = {
    "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "count": len(all_items),
    "items": all_items
}
with open("institution_data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n✅ Saved {len(all_items)} → institution_data.json")
