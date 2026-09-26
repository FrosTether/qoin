#!/usr/bin/env bash
set -euo pipefail
# Example only. Review output before any deploy.
python3 -m qoin_maker.cli generate \
  --name "Harbor Qoin" \
  --symbol HQN \
  --supply 1000000 \
  --burnable \
  --chain base \
  --out ./examples/harbor-qoin
