#!/usr/bin/env python3
"""
T8e: Runner de tests d'integració. Scripts Python purs (NO pytest).
Executa cada test_*.py de testing/integration/ com a script.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTEGRATION_DIR = os.path.join(os.path.dirname(__file__), "integration")


def main():
    if not os.path.isdir(INTEGRATION_DIR):
        return True
    tests = sorted(f for f in os.listdir(INTEGRATION_DIR) if f.startswith("test_") and f.endswith(".py"))
    if not tests:
        return True
    ok = True
    for f in tests:
        path = os.path.join(INTEGRATION_DIR, f)
        print(f"\n=== {f} ===")
        r = subprocess.run(
            [sys.executable, path],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": ROOT},
        )
        if r.returncode != 0:
            ok = False
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
