import json, os, time
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app import ai

DATA = Path(os.environ.get("DATA_DIR", "data"))
for d in ("pdfs", "photos"):
    (DATA / d).mkdir(parents=True, exist_ok=True)
app = FastAPI()
_c = {"m": 0, "plans": []}

def plans():
    p = DATA / "floorplans.json"
    m = p.stat().st_mtime
    if m != _c["m"]:  # reloads automatically when the file changes
        _c["plans"] = [x for x in json.loads(p.read_text("utf-8")) if x.get("show_on_kiosk")]
        _c["m"] = m
    return _c["plans"]

def local(kind, pid, exts):
    for e in exts:
        if (DATA / kind / f"{pid}.{e}").exists():
            return f"/files/{kind}/{pid}.{e}"

def view(x, full=False):
    tours = [{"label": l, "url": x[k]} for l, k in
             (("Walk-through tour", "matterport_url"), ("360 rendering", "render360_url"), ("3D tour", "other_tour_url")) if x.get(k)]
    d = {"id": x["id"], "name": x["display_name"], "mfr": x["manufacturer"], "series": x["series"],
         "beds": x["bedrooms"], "baths": x["bathrooms"], "sqft": x["sqft"], "sections": x["sections"],
         "width": x["width_ft"], "length": x["length_ft"],
         "photo": local("photos", x["id"], ["webp", "jpg", "jpeg", "png"]) or x.get("photo_main"),
         "pdf": local("pdfs", x["id"], ["pdf"]) or x.get("pdf_url"), "tours": tours}
    if full:
        d["description"] = x.get("description"); d["specs"] = x.get("specs", {})
    return d

@app.get("/api/plans")
def list_plans():
    return [view(x) for x in plans()]

@app.get("/api/plans/{pid}")
def one_plan(pid: str):
    for x in plans():
        if x["id"] == pid:
            return view(x, True)
    raise HTTPException(404)

class Lead(BaseModel):
    name: str
    phone: str
    favorites: list[str] = []

@app.post("/api/lead")
def lead(l: Lead):
    with open(DATA / "leads.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), **l.model_dump()}) + "\n")
    return {"ok": True}

class Chat(BaseModel):
    messages: list[dict]

@app.post("/api/chat")
def chat(c: Chat):
    return ai.respond(plans(), c.messages, DATA)

app.mount("/files/pdfs", StaticFiles(directory=DATA / "pdfs"))
app.mount("/files/photos", StaticFiles(directory=DATA / "photos"))
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True))
