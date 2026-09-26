"""Command line interface for Qoin Maker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __license__, __version__
from .scaffold import TokenSpec, write_project
from .validate import SpecError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="qoin-maker",
        description="Generate a standard ERC-20 Foundry project. Source-available; Production Use may require a paid license.",
    )
    p.add_argument("--version", action="version", version=f"qoin-maker {__version__} ({__license__})")

    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Write a token project to disk")
    g.add_argument("--name", required=True, help='Token name, e.g. "Harbor Qoin"')
    g.add_argument("--symbol", required=True, help="Ticker, e.g. HQN")
    g.add_argument("--decimals", type=int, default=18)
    g.add_argument("--supply", type=int, default=1_000_000, help="Initial whole-token supply")
    g.add_argument("--mintable", action="store_true")
    g.add_argument("--burnable", action="store_true")
    g.add_argument("--capped", action="store_true")
    g.add_argument("--cap", type=int, default=None, help="Max whole-token supply (defaults to --supply)")
    g.add_argument("--no-ownable", action="store_true", help="Disable owner (ignored if mintable)")
    g.add_argument("--chain", default="base", help="Hint used in generated README")
    g.add_argument("--out", default="out-token", help="Output directory")

    sub.add_parser("license", help="Print license and commercial summary")
    sub.add_parser("pricing", help="Print pricing summary")

    e = sub.add_parser("explain", help="Print JSON spec without writing files")
    e.add_argument("--name", required=True)
    e.add_argument("--symbol", required=True)
    e.add_argument("--decimals", type=int, default=18)
    e.add_argument("--supply", type=int, default=1_000_000)
    e.add_argument("--mintable", action="store_true")
    e.add_argument("--burnable", action="store_true")
    e.add_argument("--capped", action="store_true")
    e.add_argument("--cap", type=int, default=None)
    e.add_argument("--no-ownable", action="store_true")
    e.add_argument("--chain", default="base")
    return p


def _spec_from_args(args: argparse.Namespace, out: str = "out-token") -> TokenSpec:
    return TokenSpec(
        name=args.name,
        symbol=args.symbol,
        decimals=args.decimals,
        initial_supply=args.supply,
        mintable=args.mintable,
        burnable=args.burnable,
        capped=args.capped,
        cap=args.cap,
        ownable=not args.no_ownable,
        chain=args.chain,
        out_dir=Path(out),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "license":
        print(
            "Qoin Maker Source-Available License (QMSAL) 1.0\n"
            "Community use: evaluation, education, and tiny experiments.\n"
            "Production Use above $10k trailing revenue, agency work, or SaaS wrapping\n"
            "requires a Commercial License. See LICENSE, COMMERCIAL_LICENSE.md, PRICING.md."
        )
        return 0
    if args.cmd == "pricing":
        print(
            "Community  $0\n"
            "Starter     $149 once   (1 project, 1 chain)\n"
            "Studio      $499 / year (unlimited own projects, 5 chains)\n"
            "Agency      $2,490 / year (client work + white-label)\n"
            "Enterprise  from $8,000 / year\n"
            "See PRICING.md"
        )
        return 0
    try:
        if args.cmd == "explain":
            spec = _spec_from_args(args).normalized()
            print(
                json.dumps(
                    {
                        "name": spec.name,
                        "symbol": spec.symbol,
                        "decimals": spec.decimals,
                        "initial_supply": spec.initial_supply,
                        "features": spec.features,
                        "ident": spec.ident,
                        "chain": spec.chain,
                        "license": __license__,
                    },
                    indent=2,
                )
            )
            return 0
        spec = _spec_from_args(args, args.out)
        root = write_project(spec)
        print(f"Wrote {root.resolve()}")
        print("Review src/*.sol before you deploy. This is not legal advice.")
        print("Production Use may require a paid license — run: qoin-maker license")
        return 0
    except (SpecError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
