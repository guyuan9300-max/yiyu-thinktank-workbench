from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.workspace_query_router import route_workspace_query


def test_preference_question_about_article_does_not_route_to_file_search() -> None:
    route = route_workspace_query(prompt="你最喜欢顾源源文章当中的哪一篇", client_id="client_1")

    assert route.workflow == "synthesis"
    assert route.generationMode != "no_generation"
    assert route.shouldGenerateAnswer is True


def test_explicit_article_source_search_still_routes_to_file_search() -> None:
    route = route_workspace_query(prompt="帮我找顾源源文章的原文", client_id="client_1")

    assert route.workflow == "file_search"
    assert route.generationMode == "no_generation"
