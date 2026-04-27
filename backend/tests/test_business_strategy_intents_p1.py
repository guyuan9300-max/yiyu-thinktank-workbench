from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.analysis_context import infer_page_intent


def test_core_business_question_routes_to_business_profile():
    intent = infer_page_intent("CFFC 核心业务是什么？", "workspace_chat")
    assert intent.intent == "business_profile"


def test_latest_strategy_question_routes_to_strategy_profile():
    intent = infer_page_intent("日慈的最新战略是什么？", "workspace_chat")
    assert intent.intent == "strategy_profile"
