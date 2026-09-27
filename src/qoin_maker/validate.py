"""Input validation for token parameters."""

from __future__ import annotations

import re

_NAME_RE = re.compile(r"^[\w .:&+\-]{1,64}$", re.UNICODE)
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9]{0,10}$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SpecError(ValueError):
    pass


def require_name(name: str) -> str:
    name = name.strip()
    if not _NAME_RE.match(name):
        raise SpecError(
            "Token name must be 1-64 characters: letters, numbers, spaces, .:&+-"
        )
    return name


def require_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not _SYMBOL_RE.match(symbol):
        raise SpecError("Symbol must be 1-11 chars, start with a letter, A-Z / 0-9 only")
    return symbol


def require_decimals(decimals: int) -> int:
    if decimals < 0 or decimals > 18:
        raise SpecError("Decimals must be between 0 and 18")
    return decimals


def require_supply(supply: int, allow_zero: bool = False) -> int:
    if supply < 0 or (supply == 0 and not allow_zero):
        raise SpecError(
            "Initial supply must be a positive integer (whole tokens); "
            "0 is allowed only with --mintable (a wrapped or pegged token)"
        )
    if supply > 10**27:
        raise SpecError("Initial supply is implausibly large")
    return supply


def solidity_identifier(name: str, fallback: str = "GeneratedToken") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "", name)
    if not cleaned or not _IDENT_RE.match(cleaned):
        return fallback
    if cleaned[0].isdigit():
        return fallback
    return cleaned
