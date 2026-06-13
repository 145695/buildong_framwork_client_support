import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import script as inf 

PROCEED_URL = os.environ.get("PROCEED_URL", "/maces_interface.html")
RETURN_URL = os.environ.get("RETURN_URL", "/") # voice assistant url


BASE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="MACES Loan Agent")
print("Loading artifacts...")
ARTS = inf.load_artifacts()         
print("Ready.")

def to_bool(v): return str(v).strip().lower() in ("1","true","on","yes")

@app.get("/", response_class=HTMLResponse)
def home():
    with open(os.path.join(BASE, "loan_option_interface.html"), encoding="utf-8") as f:
        html = f.read()
    return html.replace("__PROCEED_URL__", PROCEED_URL).replace("__RETURN_URL__", RETURN_URL)

@app.get("/{page}.html")
def page(page: str):
    return FileResponse(os.path.join(BASE, f"{page}.html"))

@app.get("/{fname}.png")
def image(fname: str):
    return FileResponse(os.path.join(BASE, f"{fname}.png"))

@app.get("/{fname}.jpg")
def image(fname: str):
    return FileResponse(os.path.join(BASE, f"{fname}.jpg"))

@app.post("/predict")
async def predict(req: Request):
    d = await req.json()
    try:
        raw = {
            "AGE": int(d["AGE"]), "SEXE": d["SEXE"], "PROFESSION": d["PROFESSION"],
            "DEPENDENTS": int(float(d["DEPENDENTS"])),
            "INCOME": float(str(d["INCOME"]).replace(" ", "")),
            "TYPE_CREDIT": d.get("TYPE_CREDIT", ""),
            "MONTANT_CREDIT": float(str(d["MONTANT_CREDIT"]).replace(" ", "")),
            "DUREE_CREDIT": int(d["DUREE_CREDIT"]),
            "IS_BONIFIE": to_bool(d.get("_bonifie", d.get("IS_BONIFIE", 0))),
            "IS_LPP":     to_bool(d.get("_lpp",     d.get("IS_LPP", 0))),
            "EPARGNANT":  to_bool(d.get("EPARGNANT", 0)),
        }
    except (ValueError, KeyError) as e:
        return JSONResponse({"error": f"Invalid or missing field: {e}"}, status_code=400)

    result = inf.predict_applicant(raw, ARTS)
    if result is None:
        return JSONResponse({"error": "Validation failed"}, status_code=400)

    import numpy as np
    def clean(o):
        if isinstance(o, dict):  return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [clean(v) for v in o]
        if isinstance(o, np.floating): return float(o)
        if isinstance(o, np.integer):  return int(o)
        if isinstance(o, np.bool_):    return bool(o)
        return o
    return JSONResponse(clean(result))