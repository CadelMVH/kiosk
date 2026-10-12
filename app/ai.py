import json, os, time, urllib.request
URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")

def ollama(messages, fmt=None, temp=0.2):
    body = {"model": MODEL, "messages": messages, "stream": False, "keep_alive": "30m",
            "options": {"temperature": temp, "num_ctx": 4096}}
    if fmt: body["format"] = fmt
    req = urllib.request.Request(URL + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))["message"]["content"]

I = {"type": "integer"}
SCHEMA = {"type": "object", "required": ["beds_min", "beds_max", "baths_min", "sqft_min", "sqft_max", "builder", "sections", "keywords", "wants_human"],
          "properties": {"beds_min": I, "beds_max": I, "baths_min": I, "sqft_min": I, "sqft_max": I,
                         "builder": {"type": "string", "enum": ["", "Golden West", "Marlette", "Clayton Homes"]},
                         "sections": {"type": "string", "enum": ["", "Single", "Double", "Triple"]},
                         "keywords": {"type": "array", "items": {"type": "string"}}, "wants_human": {"type": "boolean"}}}
EXTRACT = ("You turn a home shopper's words into search filters for manufactured homes. Use 0 or an empty string for anything not mentioned. "
           "Count the people they mention and set beds_min to the bedrooms they need (a couple plus a parent needs 3). "
           "'Small' means sqft_max 1000. 'Big' or 'spacious' means sqft_min 1500. keywords are concrete feature words only (porch, island, office, storage). "
           "wants_human is true if they ask for a person. Use the whole conversation, so later messages refine earlier ones. Answer with JSON only.")
REPLY = ("You are a friendly helper at a manufactured home dealership kiosk, speaking out loud to a customer. Reply in 2 or 3 short sentences of plain spoken English, "
         "no lists, no markdown. Only mention the homes listed below and only use the facts given. Never mention prices, financing, or features that are not listed. "
         "If the matches are marked as closest matches, say so honestly. If there are no homes, say so and suggest changing one requirement. "
         "If there is no search yet, greet them and ask how many people will live there and how many bedrooms they want. "
         "Otherwise end by inviting them to tap a home or tell you what to change. If they asked for a person, tell them to tap Talk to someone.")

def ok(p, c, lvl):
    b, ba, s = p["bedrooms"] or 0, p["bathrooms"] or 0, p["sqft"] or 0
    if lvl < 3:
        if c["beds_min"] and b < c["beds_min"]: return False
        if c["beds_max"] and b > c["beds_max"]: return False
        if c["baths_min"] and ba < c["baths_min"]: return False
    elif c["beds_min"] and b < c["beds_min"] - 1: return False
    if lvl < 2:
        if c["sqft_min"] and s < c["sqft_min"]: return False
        if c["sqft_max"] and s > c["sqft_max"]: return False
    if lvl < 1:
        if c["builder"] and p["manufacturer"] != c["builder"]: return False
        if c["sections"] and p["sections"] != c["sections"]: return False
    return True

def hits(p, kw):
    t = (p["display_name"] + " " + (p.get("description") or "") + " " + json.dumps(p.get("specs", {}))).lower()
    return sum(k.lower() in t for k in kw)

def respond(plans, msgs, data):
    msgs = [{"role": m["role"], "content": str(m["content"])[:500]} for m in msgs[-6:] if m.get("role") in ("user", "assistant")]
    try:
        c = json.loads(ollama([{"role": "system", "content": EXTRACT}] + msgs, SCHEMA, 0))
        for k in ("beds_min", "beds_max", "baths_min", "sqft_min", "sqft_max"): c[k] = int(c.get(k) or 0)
        kw = [str(k) for k in c.get("keywords") or []]
        searched = any(c[k] for k in ("beds_min", "beds_max", "baths_min", "sqft_min", "sqft_max", "builder", "sections")) or kw
        res, lvl = [], 0
        if searched:
            for lvl in range(4):
                res = [p for p in plans if ok(p, c, lvl)]
                if res: break
            target = c["sqft_min"] or c["sqft_max"] or 0
            res = sorted(res, key=lambda p: (-hits(p, kw), abs((p["sqft"] or 0) - target)))[:6]
        facts = "\n".join(f"- {p['display_name']} ({p['manufacturer']} {p['series']}): {p['bedrooms']} bed, {p['bathrooms']} bath, {p['sqft']} sq ft"
                          + (", has a 3D tour" if p.get("matterport_url") or p.get("render360_url") or p.get("other_tour_url") else "") for p in res)
        status = "No search yet." if not searched else ("Exact matches:" if lvl == 0 else "Closest matches (not exact):") if res else "No homes found."
        reply = ollama([{"role": "system", "content": REPLY},
                        {"role": "user", "content": f"Customer said: {msgs[-1]['content']}\nPeople want a person: {c['wants_human']}\n{status}\n{facts}"}], None, 0.4).strip()
        with open(data / "searches.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "said": msgs[-1]["content"], "filters": c, "found": len(res)}) + "\n")
        return {"reply": reply, "ids": [p["id"] for p in res] if searched else None}
    except Exception as e:
        return {"reply": "Sorry, I'm having trouble right now. You can use the choices on the left, or tap Talk to someone.", "ids": None, "error": str(e)[:200]}
