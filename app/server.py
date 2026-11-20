"""
server.py -- the Firmix demo web app (Flask).

Tab 1  "Analyze your code": runs the deterministic code-facts rules (tree-sitter) on pasted STM32F4 C code and
       compiles it with arm-none-eabi-gcc. NO LLM runs here, so this is the 'rules only' row of the results
       table (84% precision / 95% recall on the benchmark), not the full agent system.
Tab 2  "Benchmark replay": real recorded outputs. Test files = the pinned, pre-registered run. Dev files = full
       traces (tuned on, so not a result).
"""
import json
import os
import secrets
import tempfile
from pathlib import Path

WORK = Path(tempfile.mkdtemp(prefix="firmix_ws_"))
os.environ["FIRMIX_WORKSPACE"] = str(WORK)        # must be set before code-facts is imported

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from flask import Flask, jsonify, request, send_from_directory       # noqa: E402

from codefacts import api as cf                                      # noqa: E402
from buildtools import api as bt                                     # noqa: E402

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
MAX_SRC = 30_000
DATA = Path(__file__).parent / "demo_data.json"
_demo = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"model": "", "items": []}


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/replay")
def replay_list():
    rows = []
    for it in _demo["items"]:
        rows.append({"id": it["id"], "split": it["split"], "label": it["label"],
                     "bug_type": it["truth"]["bug_type"], "n_reported": len(it["reported"]),
                     "n_correct": sum(1 for r in it["reported"] if r["correct"])})
    return jsonify({"model": _demo["model"], "items": rows})


@app.get("/api/replay/<fid>")
def replay_one(fid):
    for it in _demo["items"]:
        if it["id"] == fid:
            return jsonify(it)
    return jsonify({"error": "unknown file"}), 404


@app.post("/api/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    src = str(body.get("source", "")).replace("\r\n", "\n")
    if not src.strip():
        return jsonify({"error": "paste some C code first"}), 400
    if len(src) > MAX_SRC:
        return jsonify({"error": f"too long: limit is {MAX_SRC} characters"}), 400
    try:
        bt.runner.check_source_safe(src)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    p = WORK / f"u_{secrets.token_hex(6)}.c"
    p.write_bytes(src.encode("utf-8"))
    try:
        cands = cf.get_candidates(str(p))["candidates"]
        lines = cf.load(str(p)).lines
        for c in cands:
            c["code"] = lines[c["line"] - 1].strip() if 1 <= c["line"] <= len(lines) else ""
        try:
            comp = bt.compile_source(src, "pasted.c")
        except Exception as e:
            comp = {"ok": False, "errors": [{"line": 0, "msg": str(e)}], "warnings": []}
        return jsonify({"candidates": cands, "compile": comp})
    except Exception as e:
        return jsonify({"error": f"could not analyse this code: {e}"}), 400
    finally:
        try:
            p.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
