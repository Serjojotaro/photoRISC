from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class APIError(Exception):
    status_code: int
    code: str
    title: str
    detail: str
