"""Run: python -m hub.scripts.inspect_brain

Prints the real signature of every public function in the Brain's compliance_agent.py
and feedback_agent.py, so you can fill in BRAIN_COMPLIANCE_FUNC / BRAIN_DECISION_FUNC in
.env correctly instead of guessing. Imports the Brain; changes nothing.
"""
from __future__ import annotations

import importlib
import inspect
import os
import sys

from ..config import get_hub_settings


def main() -> int:
    settings = get_hub_settings()
    if not settings.brain_path:
        print("Set BRAIN_PATH in .env to the folder containing compliance_agent.py first.")
        return 1
    path = os.path.abspath(settings.brain_path)
    if path not in sys.path:
        sys.path.insert(0, path)
    print(f"Inspecting the Brain at: {path}\n")
    for mod_name in ("compliance_agent", "feedback_agent"):
        try:
            module = importlib.import_module(mod_name)
        except ImportError as exc:
            print(f"[{mod_name}] could not import: {exc}\n")
            continue
        print(f"=== {mod_name}.py ===")
        found = False
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("_") or func.__module__ != mod_name:
                continue
            found = True
            print(f"  {mod_name}:{name}{inspect.signature(func)}")
        if not found:
            print("  (no top-level functions found)")
        print()
    print("Copy the 'module:function' text for the right function into .env as")
    print("BRAIN_COMPLIANCE_FUNC=... and BRAIN_DECISION_FUNC=... (the latter is optional).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
