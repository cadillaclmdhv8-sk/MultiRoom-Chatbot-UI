"""Talking to the KoboldCpp / KoboldAI generate API."""
from __future__ import annotations

import threading

import requests
from PySide6.QtCore import QObject, Signal, Slot

from .prompt import INSTRUCT_PRESETS

# Values copied from KoboldAI Lite's presets
SAMPLER_PRESET_VALUES = {
    "Godlike": {
        "temperature": 0.7, "top_p": 0.5, "top_k": 0, "top_a": 0.75, "typical": 0.19,
        "tfs": 0.97, "rep_pen": 1.1, "rep_pen_range": 1024, "rep_pen_slope": 0.7,
        "sampler_order": [6, 5, 4, 3, 2, 1, 0],
    },
    "Liminal Drift": {
        "temperature": 0.66, "top_p": 1, "top_k": 0, "top_a": 0.96, "typical": 0.6,
        "tfs": 1, "rep_pen": 1.1, "rep_pen_range": 1024, "rep_pen_slope": 0.7,
        "sampler_order": [6, 4, 5, 1, 0, 2, 3],
    },
}
GODLIKE = SAMPLER_PRESET_VALUES["Godlike"]

SAMPLER_PRESETS = list(SAMPLER_PRESET_VALUES) + ["Custom"]

# Extra stop strings per instruct format, so the model doesn't start a new turn
_INSTRUCT_STOPS = {
    "Mistral": ["[INST]", "</s>"],
    "ChatML": ["<|im_end|>", "<|im_start|>"],
    "Llama 3": ["<|eot_id|>", "<|start_header_id|>"],
    "Alpaca": ["### Instruction"],
}


def sampler_from_settings(s: dict) -> dict:
    preset = s.get("sampler_preset", "Godlike")
    sampler = dict(SAMPLER_PRESET_VALUES.get(preset, GODLIKE))
    if preset == "Custom":
        sampler["temperature"] = float(s.get("temperature", 0.7))
    return sampler


def instruct_from_settings(s: dict) -> tuple[str, str]:
    preset = s.get("instruct_preset", "Mistral")
    if preset == "Custom":
        return (s.get("instruct_start", ""), s.get("instruct_end", ""))
    return INSTRUCT_PRESETS.get(preset, ("", ""))


def stops_from_settings(s: dict) -> list[str]:
    user = s.get("user_name", "You")
    stops = [f"[{user}]:", f"\n[{user}]", "\n###"]
    stops += _INSTRUCT_STOPS.get(s.get("instruct_preset", ""), [])
    return stops


class KoboldClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.strip().rstrip("/")

    def model_name(self, timeout: float = 4) -> str:
        r = requests.get(f"{self.base_url}/api/v1/model", timeout=timeout)
        r.raise_for_status()
        return r.json().get("result", "?")

    def max_context(self, timeout: float = 4) -> int:
        try:
            r = requests.get(f"{self.base_url}/api/v1/config/max_context_length", timeout=timeout)
            r.raise_for_status()
            return int(r.json().get("value", 4096))
        except Exception:
            return 4096

    def abort(self) -> None:
        try:
            requests.post(f"{self.base_url}/api/extra/abort", json={}, timeout=3)
        except Exception:
            pass

    def generate(self, prompt: str, max_length: int, max_context: int,
                 sampler: dict, stop: list[str]) -> str:
        payload = {
            "prompt": prompt,
            "max_length": max_length,
            "max_context_length": max_context,
            "stop_sequence": stop,
            "trim_stop": True,
            **sampler,
        }
        r = requests.post(f"{self.base_url}/api/v1/generate", json=payload, timeout=900)
        r.raise_for_status()
        results = r.json().get("results") or [{}]
        return results[0].get("text", "")


def run_background(fn, on_done=None, on_error=None) -> "BackgroundCall":
    """Run fn() on a daemon thread; callbacks run on the Qt main thread.

    Must be called from the main thread.
    """
    call = BackgroundCall(fn, on_done, on_error)
    call.start()
    return call


class BackgroundCall(QObject):
    # Connected to slots on this object (which lives in the main thread),
    # so emitting from the worker thread queues the call to the main thread.
    _done = Signal(object)
    _error = Signal(object)

    _alive: set["BackgroundCall"] = set()  # keep a reference until finished

    def __init__(self, fn, on_done=None, on_error=None):
        super().__init__()
        self._fn = fn
        self._on_done = on_done
        self._on_error = on_error
        self._done.connect(self._handle_done)
        self._error.connect(self._handle_error)

    def start(self):
        BackgroundCall._alive.add(self)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            result = self._fn()
        except Exception as e:  # noqa: BLE001
            self._error.emit(e)
        else:
            self._done.emit(result)

    @Slot(object)
    def _handle_done(self, result):
        BackgroundCall._alive.discard(self)
        if self._on_done:
            self._on_done(result)

    @Slot(object)
    def _handle_error(self, e):
        BackgroundCall._alive.discard(self)
        if self._on_error:
            self._on_error(e)


def describe_error(e: Exception, url: str) -> str:
    if isinstance(e, requests.ConnectionError):
        return f"Can't reach KoboldAI at {url}. Is it running?"
    if isinstance(e, requests.Timeout):
        return "KoboldAI took too long to answer."
    return f"KoboldAI error: {e}"
