"""重排（rerank）层的单元测试。

覆盖三条保证：
  1. 模式解析必须是"诚实降级"——不可用时退回 rule，并且报的是**实际生效**的模式，
     否则一个分数会被记到并没有真正打分的裁判头上。
  2. 交给 LLM 裁判的载荷是"紧凑视图"，不含简历全文（隐私与成本）。
  3. 解释（explain）失败时降级为规则摘要，不能让整次检索失败。
"""

from types import SimpleNamespace

from app.schemas import CandidateExtract, JobRequirements, MatchExplanation
from app.services.llm import ModelService
from app.services.search import _candidate_payload, resolve_rerank_mode


def _settings(model_mode: str = "deepseek", chat_key: str = "sk-test", rerank_mode: str = "rule"):
    return SimpleNamespace(
        model_mode=model_mode,
        chat_api_key=chat_key,
        rerank_mode=rerank_mode,
        rerank_top_n=20,
    )


def test_unknown_mode_falls_back_to_rule():
    assert resolve_rerank_mode(_settings(), "cross-encoder") == "rule"
    assert resolve_rerank_mode(_settings(), "") == "rule"


def test_llm_downgrades_when_chat_model_unreachable():
    # 离线演示（mock）或没配 Key 时，不能因为选了 llm 就让检索失败
    assert resolve_rerank_mode(_settings(model_mode="mock"), "llm") == "rule"
    assert resolve_rerank_mode(_settings(chat_key=""), "llm") == "rule"


def test_llm_kept_when_a_chat_model_exists():
    assert resolve_rerank_mode(_settings(), "llm") == "llm"


def test_request_overrides_env_default():
    assert resolve_rerank_mode(_settings(rerank_mode="llm"), "rule") == "rule"
    assert resolve_rerank_mode(_settings(rerank_mode="rule"), "llm") == "llm"


def test_candidate_payload_is_compact_and_keyed():
    candidate = SimpleNamespace(
        id="cand-1", current_title="销售总监", years_experience=12, location="上海",
        industries=["半导体"], skills=["大客户", "渠道"], management_experience=True,
    )
    data = CandidateExtract(name="张三")
    payload = _candidate_payload(candidate, data, "某晶圆厂大客户销售，年销售额 1.6 亿元")

    assert payload["key"] == "cand-1"
    assert payload["current_title"] == "销售总监"
    assert payload["management"] is True
    # 紧凑视图：证据被截断，不带整份简历
    assert len(payload["evidence"]) <= 600
    assert "summary" in payload and len(payload["summary"]) <= 200


def test_explain_falls_back_instead_of_raising(monkeypatch):
    service = ModelService(db=None)

    def boom(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(service, "_structured", boom)
    monkeypatch.setattr(service, "_audit", lambda *args, **kwargs: None)

    result = service.explain(JobRequirements(title="半导体销售总监", industries=["半导体"]), CandidateExtract(name="张三"), ["证据文本"])

    assert isinstance(result, MatchExplanation), "解释失败必须返回可用的降级结果，而不是抛异常"
