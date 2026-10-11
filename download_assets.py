"""Downloads floorplan PDFs and main photos so the kiosk works without GitHub/Wix. Safe to re-run."""
import json, os, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
DATA = Path(os.environ.get("DATA_DIR", "data"))
plans = [p for p in json.loads((DATA / "floorplans.json").read_text("utf-8")) if p.get("show_on_kiosk")]
jobs = []
for p in plans:
    if p.get("pdf_url"): jobs.append((p["id"], "PDF", p["pdf_url"], DATA / "pdfs" / f"{p['id']}.pdf"))
    if p.get("photo_main"):
        ext = p["photo_main"].rsplit(".", 1)[-1].lower()
        jobs.append((p["id"], "photo", p["photo_main"], DATA / "photos" / f"{p['id']}.{ext}"))
def get(j):
    pid, kind, url, dest = j
    if dest.exists(): return (pid, kind, url, "already have")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        body = urllib.request.urlopen(req, timeout=30).read()
        if kind == "PDF" and not body.startswith(b"%PDF"): return (pid, kind, url, "FAILED: not a PDF")
        dest.write_bytes(body); return (pid, kind, url, "ok")
    except Exception as e:
        return (pid, kind, url, f"FAILED: {e}")
with ThreadPoolExecutor(8) as ex: res = list(ex.map(get, jobs))
bad = [r for r in res if r[3].startswith("FAILED")]
lines = [f"{r[0]}  {r[1]}  {r[3]}  {r[2]}" for r in bad]
(DATA / "download_report.txt").write_text("\n".join(lines) or "All downloads succeeded.", encoding="utf-8")
print(f"{len(res)-len(bad)} of {len(res)} files ready. {len(bad)} failed - see data/download_report.txt")
