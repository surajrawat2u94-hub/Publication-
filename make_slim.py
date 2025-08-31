# make_slim.py
import json, gzip

HOME_ROR = '04q2jes40'
HOME_KW  = ('university of petroleum', 'energy studies', 'upes')

def derive_authors(w):
    out=[]
    for a in (w.get('authorships') or []):
        nm = (a.get('author') or {}).get('display_name') or a.get('display_name')
        if nm: out.append(str(nm))
    return out

def derive_home_authors(w):
    out=set()
    for a in (w.get('authorships') or []):
        nm = (a.get('author') or {}).get('display_name') or a.get('display_name')
        if not nm: continue
        insts = a.get('institutions') or []
        match_ror = any((i.get('ror','').split('/')[-1] or '').lower()==HOME_ROR for i in insts)
        match_kw  = any(k in (i.get('display_name','').lower()) for i in insts for k in HOME_KW)
        if match_ror or match_kw: out.add(str(nm))
    return sorted(out)

def subjects(w, k=6):
    out=[]
    for c in (w.get('concepts') or []):
        nm = c.get('display_name') or c.get('name')
        if nm: out.append(str(nm))
        if len(out) >= k: break
    return out

def issns(w):
    out=set()
    def add(v):
        if isinstance(v, list):
            for x in v: add(x)
        elif isinstance(v, str) and v.strip():
            out.add(v.strip())
    hv = w.get('host_venue') or {}
    pl = w.get('primary_location') or {}
    srcs = [hv, hv.get('source') or {}, pl.get('source') or {}]
    for s in srcs:
        for key in ('issn_l','issn','issn_print','issn_electronic'):
            add(s.get(key))
    return sorted(out)

def publisher(w):
    return (w.get('publisher') or
            (w.get('host_venue') or {}).get('publisher') or
            (w.get('primary_location') or {}).get('source', {}).get('publisher') or '')

with open('institution_data.json','r',encoding='utf-8') as f:
    J = json.load(f)

slim_items=[]
for w in (J.get('items') or []):
    slim_items.append({
        "id": w.get("id"),
        "title": w.get("display_name") or w.get("title"),
        "journal": (w.get("host_venue") or {}).get("display_name") or w.get("journal"),
        "year": w.get("publication_year") or w.get("year"),
        "type": w.get("type"),
        "type_crossref": w.get("type_crossref"),
        "citations": w.get("cited_by_count") or w.get("citations") or 0,
        "doi": w.get("doi"),
        "url": w.get("landing_page_url") or (f"https://doi.org/{w['doi']}" if w.get("doi") else w.get("url")),
        "issns": issns(w),
        "authors": derive_authors(w),            # names only
        "home_authors": derive_home_authors(w),  # names only
        "is_retracted": bool(w.get("is_retracted", False)),
        "subjects": subjects(w),                 # names only
        "publisher": publisher(w)
    })

OUT = {"updated": J.get("updated"), "count": len(slim_items), "items": slim_items}
with gzip.open('institution_data.slim.json.gz','wt',encoding='utf-8') as zf:
    json.dump(OUT, zf, ensure_ascii=False)

print("Wrote institution_data.slim.json.gz with", len(slim_items), "items")
