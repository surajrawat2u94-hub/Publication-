import json, time, sys, urllib.parse, urllib.request, ssl

# ==== YOUR SETTINGS (already filled) ====
ROR = "04q2jes40"
CONTACT = "surajrawat.2u94@gmail.com"
FROM = "2010-01-01"
TO   = f"{time.gmtime().tm_year}-12-31"

# Start conservative (avoid throttling). Will auto-drop further if needed.
PER_PAGE_START = 25
PAGES_MAX = 200
BASE = "https://api.openalex.org/works"
UA   = f"Institution Sync (+mailto:{CONTACT})"
# ========================================

def log(msg): print(msg, flush=True)
def redacted(u: str) -> str:
    return u.replace(urllib.parse.quote(CONTACT), "hidden%40example.org")

def get_page(cursor, per_page):
    # host_venue is NOT allowed in select anymore — use primary_location/locations.
    params = {
        "per-page": str(per_page),
        "cursor": cursor,
        "mailto": CONTACT,
        "filter": f"institutions.ror:{ROR},from_publication_date:{FROM},to_publication_date:{TO}",
        "select": "id,doi,title,authorships,publication_year,type,cited_by_count,primary_location,locations,is_retracted",
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    log("GET " + redacted(url))

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "From": CONTACT,
            "Accept": "application/json",
            "Connection": "close",
        },
    )

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            body = resp.read()
            status = resp.status
            retry_after = int(resp.headers.get("Retry-After", "0") or 0)
    except urllib.error.HTTPError as e:
        status = e.code
        body   = e.read() if hasattr(e, "read") else b""
        retry_after = int(e.headers.get("Retry-After", "0") or 0)
    except Exception as e:
        log(f"❌ Network error: {e}")
        sys.exit(1)

    if status != 200:
        snippet = (body or b"")[:300].decode("utf-8", errors="ignore")
        log(f"❗ HTTP {status}. Retry-After: {retry_after}s. Body: {snippet}")
        return status, None, None, retry_after

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        log(f"❌ Invalid JSON: {e}")
        sys.exit(1)

    items = []
    for w in data.get("results", []):
        doi = (w.get("doi") or "").replace("https://doi.org/","").replace("http://doi.org/","")

        # Authors
        authors = [a.get("author",{}).get("display_name") for a in (w.get("authorships") or []) if a.get("author")]
        authors = [a for a in authors if a]

        # Journal + ISSNs from primary_location.source
        journal = ""
        issns = []
        pl = w.get("primary_location") or {}
        src = pl.get("source") or {}
        if src:
            journal = src.get("display_name") or ""
            issns = [str(x).upper() for x in (src.get("issn") or [])]

        items.append({
            "doi": doi,
            "title": w.get("title") or "",
            "year": w.get("publication_year"),
            "type": w.get("type") or "",
            "citations": w.get("cited_by_count") or 0,
            "authors": authors,
            "journal": journal,
            "issns": issns,
            "url": pl.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else ""),
            "is_retracted": bool(w.get("is_retracted")),
        })

    next_cursor = (data.get("meta") or {}).get("next_cursor")
    return 200, items, next_cursor, 0

def polite_wait(ms):
    ms = min(ms, 120000)  # cap 120s
    log(f"⏳ Waiting {ms}ms before retry…")
    time.sleep(ms/1000)

def main():
    cursor = "*"
    page = 0
    all_items = []
    per_page = PER_PAGE_START
    first_page_tries = 0

    while cursor and page < PAGES_MAX:
        page += 1
        log(f"\n🔎 Fetching page {page} (per-page={per_page}) …")
        status, items, next_cursor, retry_after = get_page(cursor, per_page)

        if status in (403, 429):
            first_page_tries += (1 if page == 1 else 0)
            backoff_ms = (retry_after * 1000) if retry_after else (1000 * (2 ** min(first_page_tries, 5)))
            polite_wait(backoff_ms)

            # On first-page throttling, try smaller per-page
            if page == 1 and per_page > 10:
                per_page = 10
                log("�� Switching to per-page=10 and retrying page 1…")
                page -= 1
                continue

            page -= 1
            continue

        if status != 200:
            log("❌ Aborting due to HTTP error.")
            sys.exit(1)

        log(f"✅ Got {len(items)} items")
        all_items.extend(items)
        if not items:
            break
        cursor = next_cursor
        time.sleep(0.3)

    out = {"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "count": len(all_items), "items": all_items}
    with open("institution_data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log(f"\n💾 Saved {len(all_items)} → institution_data.json")

if __name__ == "__main__":
    main()
