"""
llm.py -- thin client for a local Ollama model. Standard library only.

All LLM-based setups go through this one class with the pinned settings in config.py.
`chat()` returns {"message": {...}, "prompt_tokens": n, "completion_tokens": n} so cost is
countable. `fmt` is an optional JSON schema: Ollama then forces the answer to match it.
"""
from __future__ import annotations

import json
import urllib.request

from . import config as C


class LLMError(RuntimeError):
    pass


class OllamaLLM:
    def __init__(self, model: str | None = None, seed: int | None = None, temperature: float | None = None):
        self.model = model or C.MODEL
        self.options = dict(C.OPTIONS)
        if seed is not None:                      # only for run-to-run variation studies; default = pinned seed
            self.options["seed"] = seed
        if temperature is not None:               # only for the sampled-robustness study; default = pinned 0
            self.options["temperature"] = temperature
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    def chat(self, messages, tools=None, fmt=None) -> dict:
        body = {"model": self.model, "messages": messages, "stream": False,
                "think": C.THINK, "options": self.options}
        if tools:
            body["tools"] = tools
        if fmt:
            body["format"] = fmt
        req = urllib.request.Request(C.OLLAMA_URL + "/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=C.REQUEST_TIMEOUT_S) as r:
                data = json.loads(r.read())
        except Exception as e:                          # connection refused, timeout, ...
            raise LLMError(f"Ollama call failed: {e}") from e
        pt, ct = data.get("prompt_eval_count", 0), data.get("eval_count", 0)
        self.prompt_tokens += pt
        self.completion_tokens += ct
        self.calls += 1
        return {"message": data["message"], "prompt_tokens": pt, "completion_tokens": ct}
