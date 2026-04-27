from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse, GenerationRuntimeDecisionRecord
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / 'data')
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        '/api/v1/clients',
        json={
            'name': name,
            'alias': name,
            'domain': '公益',
            'type': '战略陪伴',
            'intro': 'workspace chat p28 finalizer',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def _mock_quality(**overrides):
    payload = {
        'hasDirectAnswer': True,
        'evidenceListOnly': False,
        'evidenceQuoteOnly': False,
        'leakedInternalMarkers': [],
        'candidateAsOfficialRisk': False,
        'officialBoundaryViolation': False,
        'missingRawEvidenceForIntent': False,
        'offTopicRisk': False,
        'factSlotHit': True,
        'factSlotMissingReason': None,
        'grade': 'pass',
        'reason': 'unit-test',
    }
    payload.update(overrides)
    return payload


def test_workspace_chat_legacy_path_writes_workspace_answer_finalization(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client, 'legacy-finalizer-p28')
    client.app.state.app_state.db.set_setting('workspace_chat_data_center_primary', '0')

    monkeypatch.setattr(
        app_main,
        'validate_answer_quality',
        lambda **_kwargs: _mock_quality(),
    )
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        'generate_general_fallback',
        lambda *_args, **_kwargs: AiStructuredResponse(
            content='当前资料虽有限，但已能回答核心业务与合作状态。',
            judgment='ok',
            analysis='ok',
            actions='ok',
            timeline='ok',
        ),
    )

    response = client.post(f'/api/v1/clients/{client_id}/workspace/chat', json={'prompt': '这个客户是谁？'})
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get('retrievalSummary') or {}
    finalization = retrieval_summary.get('workspaceAnswerFinalization') or {}

    assert isinstance(finalization, dict)
    assert finalization.get('shouldShowRetryBanner') is False
    assert finalization.get('userVisibleQualityStatus') in {'ready', 'usable_with_boundary', 'degraded'}


def test_workspace_chat_local_fallback_path_writes_workspace_answer_finalization(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client, 'local-fallback-finalizer-p28')
    client.app.state.app_state.db.set_setting('workspace_chat_data_center_primary', '0')

    monkeypatch.setattr(
        app_main,
        'decide_generation_runtime_policy',
        lambda *_args, **_kwargs: GenerationRuntimeDecisionRecord(
            shouldAttemptLlm=False,
            shouldUseCompactFirst=False,
            shouldUseLocalOnly=True,
            shouldQueueLongAnswerRetry=False,
            shouldProbeAfterCooldown=False,
            reason='test_local_only',
            cooldownActive=False,
        ),
    )
    monkeypatch.setattr(
        app_main,
        'validate_answer_quality',
        lambda **_kwargs: _mock_quality(),
    )
    monkeypatch.setattr(
        app_main,
        'retrieve_knowledge_bundle',
        lambda *_args, **_kwargs: RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id='kd_local_fallback_1',
                    chunk_id='chunk_local_fallback_1',
                    title='客户业务介绍',
                    excerpt='当前资料可确认，客户核心业务包括资源支持与项目服务。',
                    score=0.91,
                    coverage=0.84,
                    section_label='正文',
                    source_stage='raw_chunk',
                    drillthrough_used=True,
                    matched_terms=['核心业务', '项目服务'],
                    path='/tmp/local-fallback.md',
                )
            ],
            coverage=0.84,
            retrieval_summary={'rawChunkHitCount': 1, 'masterHitCount': 1, 'surrogateHitCount': 0},
            context_text='',
            matched_terms=['核心业务', '项目服务'],
            failure_reason=None,
        ),
    )

    response = client.post(f'/api/v1/clients/{client_id}/workspace/chat', json={'prompt': '下一步建议是什么？'})
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get('retrievalSummary') or {}
    finalization = retrieval_summary.get('workspaceAnswerFinalization') or {}

    assert isinstance(finalization, dict)
    assert 'userVisibleQualityStatus' in finalization
    assert 'shouldShowRetryBanner' in finalization
    assert payload.get('answerMode') == 'grounded_answer'
    assert payload.get('evidenceStatus') == 'sufficient'
    assert retrieval_summary.get('answerMode') == 'grounded_answer'
    assert retrieval_summary.get('evidenceStatus') == 'sufficient'


def test_workspace_chat_intro_local_fallback_expands_profile_answer(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client, '日慈基金会')
    client.app.state.app_state.db.set_setting('workspace_chat_data_center_primary', '0')

    monkeypatch.setattr(
        app_main,
        'decide_generation_runtime_policy',
        lambda *_args, **_kwargs: GenerationRuntimeDecisionRecord(
            shouldAttemptLlm=False,
            shouldUseCompactFirst=False,
            shouldUseLocalOnly=True,
            shouldQueueLongAnswerRetry=False,
            shouldProbeAfterCooldown=False,
            reason='test_intro_local_only',
            cooldownActive=False,
        ),
    )
    monkeypatch.setattr(
        app_main,
        'validate_answer_quality',
        lambda **_kwargs: _mock_quality(),
    )
    monkeypatch.setattr(
        app_main,
        'retrieve_knowledge_bundle',
        lambda *_args, **_kwargs: RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id='kd_intro_1',
                    chunk_id='chunk_intro_1',
                    title='日慈使命愿景价值观',
                    excerpt='使命是构建普惠的关系支持系统，让孩子与青年在真实关系中获得理解、练习与支持。我们不是在拯救有问题的个体，而是在搭建一个大多数孩子都能用得上的关系保护网。',
                    score=0.96,
                    coverage=0.88,
                    section_label='正文',
                    source_stage='raw_chunk',
                    drillthrough_used=True,
                    matched_terms=['关系支持系统', '关系保护网'],
                    path='/tmp/rici-mission.md',
                ),
                CitationMatch(
                    knowledge_document_id='kd_intro_2',
                    chunk_id='chunk_intro_2',
                    title='日慈战略陪伴工作坊2天结构',
                    excerpt='这两天不是四段拼盘，而是一条连续叙事：我们是谁、为什么这样做、怎么把系统跑起来、每条业务线怎样更有积累。今年战略重点是把树放进系统/飞轮。',
                    score=0.92,
                    coverage=0.84,
                    section_label='正文',
                    source_stage='raw_chunk',
                    drillthrough_used=True,
                    matched_terms=['飞轮', '系统'],
                    path='/tmp/rici-workshop.md',
                ),
                CitationMatch(
                    knowledge_document_id='kd_intro_3',
                    chunk_id='chunk_intro_3',
                    title='日慈工作坊数字化设计规划',
                    excerpt='数字化的目标不是单纯上工具，而是让价值可被证明、让经验可被复用，并逐步沉淀流程、工具和数据价值。',
                    score=0.9,
                    coverage=0.82,
                    section_label='正文',
                    source_stage='raw_chunk',
                    drillthrough_used=True,
                    matched_terms=['数字化', '经验可被复用'],
                    path='/tmp/rici-digital.md',
                ),
                CitationMatch(
                    knowledge_document_id='kd_intro_4',
                    chunk_id='chunk_intro_4',
                    title='心灵魔法学院项目介绍',
                    excerpt='项目从预防视角出发，通过赋能在地教师，为其提供主题式、体验式、标准化的课程资料及配套培训，支持教师在学期内开展心理主题活动。',
                    score=0.94,
                    coverage=0.86,
                    section_label='正文',
                    source_stage='raw_chunk',
                    drillthrough_used=True,
                    matched_terms=['预防视角', '标准化课程资料'],
                    path='/tmp/rici-academy.md',
                ),
                CitationMatch(
                    knowledge_document_id='kd_intro_5',
                    chunk_id='chunk_intro_5',
                    title='日慈基金会-繁星计划一季度沟通会议纪要',
                    excerpt='繁星计划聚焦定位校准、公众传播、生态招募、资源库平台与工具协同，是组织对外叙事与生态联动的重要工作层。',
                    score=0.89,
                    coverage=0.8,
                    section_label='正文',
                    source_stage='raw_chunk',
                    drillthrough_used=True,
                    matched_terms=['繁星计划', '生态招募'],
                    path='/tmp/rici-fanxing.md',
                ),
            ],
            coverage=0.9,
            retrieval_summary={'rawChunkHitCount': 5, 'masterHitCount': 5, 'surrogateHitCount': 0},
            context_text='',
            matched_terms=['关系支持系统', '飞轮', '数字化'],
            failure_reason=None,
        ),
    )

    response = client.post(f'/api/v1/clients/{client_id}/workspace/chat', json={'prompt': '介绍日慈基金会'})
    assert response.status_code == 200, response.text
    payload = response.json()
    content = payload.get('content') or ''

    assert payload.get('answerMode') == 'grounded_answer'
    assert payload.get('evidenceStatus') == 'sufficient'
    assert '构建普惠的关系支持系统' in content
    assert '主题式与体验式课程资料以及配套培训' in content
    assert '价值可被证明、经验可被复用' in content
    assert '繁星计划' in content
    assert len(content) >= 900
