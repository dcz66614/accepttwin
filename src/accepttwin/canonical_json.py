"""Canonical JSON — thin re-export of the single implementation.

Single source of truth (PROJECT_BOOK §10.4, ADR-003, T009): the only
Canonical JSON implementation is
:func:`accepttwin.contract.canonical_json_bytes` (with
:func:`accepttwin.contract.canonical_contract_hash` built on it).
This module re-exports those two names — and nothing else — so
callers that think in terms of "canonical JSON" have a stable import
path without a second implementation ever existing. No sorting,
encoding, volatile-field stripping, header normalisation or port
normalisation is implemented here: every behaviour, including the
ADR-003 loopback-port-to-0 normalisation, lives in
:mod:`accepttwin.contract` and is inherited verbatim by re-export.
"""

from __future__ import annotations

from .contract import canonical_contract_hash, canonical_json_bytes

__all__ = ["canonical_contract_hash", "canonical_json_bytes"]
