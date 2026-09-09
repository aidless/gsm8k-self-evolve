"""Round-2 evolve: incumbent concise-reason -> {step-calc, rounding-aware, rectify}.
Runs on cloud with system python3 (has scipy). One model task at a time.
Usage: python3 run_evolve_round2.py  (cwd=/root/exp-gsm8k)
"""
import sys
from pathlib import Path
sys.path.insert(0, '/root/evo-agent/src')
from evoagent.core import evolve
import json

result = evolve(Path('/root/exp-gsm8k'))
print(json.dumps(result, ensure_ascii=False, indent=2))
