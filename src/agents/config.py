"""
config.py -- the ONE place that pins the LLM settings.

The same model and the same settings are used for every LLM-based setup in the evaluation
(single LLM, agents without verifier, full Firmix). Changing anything here changes all of them,
so any edit must be logged in CHANGELOG.md before a test-set run.
"""
OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3:8b"          # pinned tag, never ':latest'. Fallback if tool calls are flaky: "llama3.1:8b"
OPTIONS = {
    "temperature": 0,       # deterministic as far as the model allows
    "seed": 42,
    "num_ctx": 8192,        # small on purpose: an 8 GB GPU must keep the whole model + cache in VRAM
    "num_predict": 1024,
}
THINK = False               # qwen3 has a 'thinking' mode; off = faster, and fine for tool routing
REQUEST_TIMEOUT_S = 300
