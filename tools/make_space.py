#!/usr/bin/env python3
"""
make_space.py -- assemble ./space_build, the folder you push to a Hugging Face Space (SDK: Docker).
Run tools/export_demo.py first so app/demo_data.json exists.

    python tools/make_space.py
"""
import shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "space_build"
if not (ROOT / "app" / "demo_data.json").exists():
    sys.exit("app/demo_data.json is missing: run python tools/export_demo.py first")
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
ign = shutil.ignore_patterns("__pycache__", "*.pyc")
for d in ("app", "benchmark", "include", "src"):
    shutil.copytree(ROOT / d, OUT / d, ignore=ign)
(OUT / "tools").mkdir()
shutil.copy(ROOT / "tools" / "setup_deps.py", OUT / "tools" / "setup_deps.py")
for f in ("Dockerfile", "requirements.txt"):
    shutil.copy(ROOT / f, OUT / f)
(OUT / "README.md").write_text(
    "---\ntitle: Firmix 2.0\nemoji: 🔧\ncolorFrom: blue\ncolorTo: gray\nsdk: docker\napp_port: 7860\npinned: false\n---\n\n"
    "# Firmix 2.0 demo\n\nTool-grounded multi-agent bug finder for STM32F4 firmware. "
    "Live rules + compile check, and a replay of recorded agent runs. Full project, results and limits: "
    "see the main repository README.\n", encoding="utf-8")
print(f"built {OUT}  ({sum(1 for _ in OUT.rglob('*') if _.is_file())} files)")
