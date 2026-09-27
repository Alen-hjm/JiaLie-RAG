"""编排图（LangGraph）的单元测试。

不依赖数据库、不依赖大模型：这里只锁两件最关键的事——

1. **路由决策**：评估之后走「重查」还是「生成」。这是整张图里唯一"智能"的
   决策点，必须能用普通断言锁住。
2. **降级路径**：评估/改写节点抛异常时，必须降级为单轮通过，而不是让检索失败——
   编排层是增强项，不是依赖项。
"""

from __future__ import annotations

from app.schemas import JobRequirements
from app.services.llm import ModelService
from app.services.orchestration import GENERATE, REWRITE, decide_next


def _state(verdict: str = "good", attempt: int = 1, max_attempts: int = 2) -> dict:
    return {"grade": {"verdict": verdict}, "attempt": attempt, "max_attempts": max_attempts}


def test_good_verdict_generates_immediately():
    assert decide_next(_state("good", attempt=1)) == GENERATE


def test_weak_verdict_rewrites_when_budget_remains():
    assert decide_next(_state("weak", attempt=1, max_attempts=2)) == REWRITE


def test_weak_verdict_stops_at_retry_cap():
    # 上限就是 2 次检索：第 2 次之后即使还是 weak 也必须收口
    assert decide_next(_state("weak", attempt=2, max_attempts=2)) == GENERATE


def test_missing_grade_defaults_to_generate():
    # 评估节点异常时不允许进入重查循环，否则图可能永远转下去
    assert decide_next({"attempt": 1, "max_attempts": 2}) == GENERATE


def _broken_service(monkeypatch):
    service = ModelService(db=None)

    def boom(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(service, "_structured", boom)
    monkeypatch.setattr(service, "_audit", lambda *a, **k: None)
    return service


def test_grade_failure_degrades_to_single_pass(monkeypatch):
    """评估抛异常必须等价于 verdict=good，而不是让检索失败。"""
    from types import SimpleNamespace

    service = _broken_service(monkeypatch)
    fake_match = SimpleNamespace(
        candidate=SimpleNamespace(name="张三", current_title="销售", years_experience=5, industries=["半导体"], skills=["大客户"]),
        total_score=60,
    )
    result = service.grade_recall(JobRequirements(title="半导体销售经理"), [fake_match])
    assert result["verdict"] == "good"


def test_rewrite_failure_returns_original_query(monkeypatch):
    """改写失败必须沿用原查询，绝不把空串/异常喂回检索。"""
    service = _broken_service(monkeypatch)
    job = JobRequirements(title="半导体销售经理", industries=["半导体"])
    merged, text = service.rewrite_query(job, {"verdict": "weak", "missing": ["半导体"]}, "原始 JD 文本")

    assert merged.title == "半导体销售经理"
    assert text == "原始 JD 文本"


def test_rewrite_that_changes_nothing_skips_the_second_retrieval():
    """改写没变化就不该再查一遍——同样的查询必然得到同样的结果。"""
    from app.services.orchestration import RETRIEVE, decide_after_rewrite

    assert decide_after_rewrite({"rewritten": True}) == RETRIEVE
    assert decide_after_rewrite({"rewritten": False}) == GENERATE
    assert decide_after_rewrite({}) == GENERATE
