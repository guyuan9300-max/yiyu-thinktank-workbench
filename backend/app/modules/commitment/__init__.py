"""commitment 模块 · 承诺/交付追踪

v2.1 SSOT 落地:
- 所有读写 commitments 表的代码 → 走 CommitmentRepository
- 业务码禁止直接 SELECT FROM commitments

对外接口:Repository + types(__all__ 控制)
"""
from .types import Commitment, CommitmentStatus
from .repository import (
    CommitmentRepository,
    get_commitment_repository,
)

__all__ = [
    "Commitment",
    "CommitmentStatus",
    "CommitmentRepository",
    "get_commitment_repository",
]
