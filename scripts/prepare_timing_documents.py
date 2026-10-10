"""Create a separate unseen synthetic timing corpus, never overwrite the demo or existing trials."""
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ar_copilot.config import ROOT
from ar_copilot.generate import generate


def main():
    destination = ROOT / 'runtime' / 'timing_data'
    if destination.exists():
        raise SystemExit('Timing corpus already exists; preserved unchanged. Do not regenerate after exposure.')
    generate(destination, seed=20261011)
    print('Prepared separate fictional timing documents under runtime/timing_data. No timing observations created.')


if __name__ == '__main__':
    main()
