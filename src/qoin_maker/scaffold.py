"""Write a generated token project to disk."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .templates import deploy_script, erc20_contract, foundry_toml, token_readme
from .validate import (
    require_decimals,
    require_name,
    require_supply,
    require_symbol,
    solidity_identifier,
)


@dataclass
class TokenSpec:
    name: str
    symbol: str
    decimals: int = 18
    initial_supply: int = 1_000_000
    mintable: bool = False
    burnable: bool = False
    capped: bool = False
    cap: int | None = None
    ownable: bool = True
    chain: str = "base"
    out_dir: Path = field(default_factory=lambda: Path("out-token"))

    def normalized(self) -> "TokenSpec":
        spec = TokenSpec(
            name=require_name(self.name),
            symbol=require_symbol(self.symbol),
            decimals=require_decimals(self.decimals),
            initial_supply=require_supply(self.initial_supply),
            mintable=self.mintable,
            burnable=self.burnable,
            capped=self.capped,
            cap=require_supply(self.cap) if self.cap is not None else None,
            ownable=self.ownable or self.mintable,
            chain=self.chain.strip().lower() or "base",
            out_dir=Path(self.out_dir),
        )
        if spec.capped and spec.cap is None:
            spec.cap = spec.initial_supply
        if spec.capped and spec.cap is not None and spec.cap < spec.initial_supply:
            raise ValueError("Cap must be >= initial supply")
        return spec

    @property
    def ident(self) -> str:
        return solidity_identifier(self.name.replace(" ", ""), "GeneratedToken")

    @property
    def features(self) -> list[str]:
        flags = []
        if self.ownable:
            flags.append("ownable")
        if self.mintable:
            flags.append("mintable")
        if self.burnable:
            flags.append("burnable")
        if self.capped:
            flags.append(f"capped:{self.cap}")
        return flags


def write_project(spec: TokenSpec) -> Path:
    spec = spec.normalized()
    root = spec.out_dir
    src = root / "src"
    script = root / "script"
    src.mkdir(parents=True, exist_ok=True)
    script.mkdir(parents=True, exist_ok=True)

    source = erc20_contract(
        name=spec.name,
        symbol=spec.symbol,
        decimals=spec.decimals,
        initial_supply=spec.initial_supply,
        mintable=spec.mintable,
        burnable=spec.burnable,
        capped=spec.capped,
        cap=spec.cap,
        ownable=spec.ownable,
        version=__version__,
    )
    (src / f"{spec.ident}.sol").write_text(source, encoding="utf-8")
    (script / "Deploy.s.sol").write_text(deploy_script(spec.ident), encoding="utf-8")
    (root / "foundry.toml").write_text(foundry_toml(), encoding="utf-8")
    (root / "README.md").write_text(
        token_readme(
            name=spec.name,
            symbol=spec.symbol,
            decimals=spec.decimals,
            initial_supply=spec.initial_supply,
            features=spec.features,
            chain=spec.chain,
        ),
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("out/\ncache/\nbroadcast/\n.env\n", encoding="utf-8")
    return root
