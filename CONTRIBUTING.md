# Contributing

Community patches that improve safety, docs, tests, or conservative templates
are welcome.

Do not contribute:

- tax / reflection / honeypot / stealth-mint logic
- "sniper bot" helpers
- telemetry that phones home by default

By submitting a patch you agree it is licensed under QMSAL 1.0 (and the
Change License on the Change Date), and that Licensor may also offer it under
the Commercial License.

## Dev loop

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
```
