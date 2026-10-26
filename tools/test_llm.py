#!/usr/bin/env python3
"""Step 8 first check: can the pinned local model (a) answer and (b) call a tool correctly?
Needs Ollama running and the model pulled:  ollama pull qwen3:8b
Usage: python tools/test_llm.py        (standard library only)"""
import json, sys, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from agents import config as C


def chat(messages, tools=None):
    body = {"model": C.MODEL, "messages": messages, "stream": False,
            "think": C.THINK, "options": C.OPTIONS}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(C.OLLAMA_URL + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=C.REQUEST_TIMEOUT_S) as r:
        return json.loads(r.read())


def main():
    ok = True
    t = time.time()
    r = chat([{"role": "user", "content": "In one short sentence: what does the volatile keyword do in C?"}])
    print(f"[1] plain answer ({time.time()-t:.1f}s): {r['message']['content'].strip()[:160]}")
    ok &= bool(r["message"]["content"].strip())

    tools = [{"type": "function", "function": {
        "name": "get_priorities", "description": "Return the NVIC priority settings found in a C file.",
        "parameters": {"type": "object", "properties": {"file": {"type": "string", "description": "path of the file"}},
                       "required": ["file"]}}}]
    t = time.time()
    r = chat([{"role": "user", "content": "Which interrupt priorities does the file dev/d07.c set? Use the tool."}], tools)
    calls = r["message"].get("tool_calls") or []
    print(f"[2] tool call ({time.time()-t:.1f}s): {json.dumps(calls)[:200]}")
    good = bool(calls) and calls[0]["function"]["name"] == "get_priorities" \
        and "d07" in json.dumps(calls[0]["function"]["arguments"])
    print("    called the right tool with the right file:", good); ok &= good
    print("\nPASS" if ok else "\nFAIL")
    sys.exit(0 if ok else 1)


main()
