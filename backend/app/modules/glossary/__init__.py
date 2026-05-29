"""glossary 模块 · 客户字典/属性(完整实施)

W2 完整实施(scope 小:只 2 处 SQL,6 个 services 已有)。
现有 services/glossary_*.py 文件 W3 切到 GlossaryRepository。

对外接口:
"""
from .types import GlossaryTerm, GlossaryAttribute
from .repository import GlossaryRepository, get_glossary_repository

__all__ = [
    "GlossaryTerm",
    "GlossaryAttribute",
    "GlossaryRepository",
    "get_glossary_repository",
]
