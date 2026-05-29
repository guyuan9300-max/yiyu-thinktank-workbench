"""commitment 类型 · frozen dataclass"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CommitmentStatus = Literal["pending", "in_progress", "fulfilled", "cancelled", "blocked"]


@dataclass(frozen=True)
class Commitment:
    id: str
    client_id: str
    committer: str             # 承诺方
    recipient: str             # 接收方
    commitment_type: str       # 'delivery' / 'meeting' / 'response' / ...
    content: str
    deadline: str | None
    status: str
    related_term_ids: tuple[str, ...] = field(default_factory=tuple)
    source_type: str = ""
    source_id: str = ""
    fulfilled_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
