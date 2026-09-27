"""LangGraph 编排：检索 → 召回质量评估 →（改写重查）→ 生成。

为什么要有这一层
----------------
固定编排的 RAG 是「一条道走到黑」：检索结果再差也只能继续往下走。
这里加一个「召回质量评估」节点，由模型判断召回是否覆盖了岗位的核心条件，
不够就自动改写查询再查一次。**把「要不要重试、怎么改」这个决策交给模型**，
这就是编排图相对固定流水线的全部增量价值——也只值这么多，不要神化。

安全阀
------
重查次数用 ``max_attempts`` 硬性封顶（默认 2）。编排图最大的风险是「越改越偏」，
没有上限的自动重试等于把模型的错觉放大 N 倍。

降级
----
LangGraph 未安装、或任何一个节点抛异常时，退回单轮固定流水线（等价于跑一遍
``retrieve -> grade(通过) -> generate``），保证主链路永远可用。
"""
from __future__ import annotations

from typing import Any, TypedDict

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import JobRequirement
from ..schemas import JobRequirements
from .llm import ModelService
from .search import search_job

# 自动重查的上限。第一次检索 + 最多 1 次改写重查。
MAX_ATTEMPTS = 2

# 节点名，避免字符串散落各处
RETRIEVE = "retrieve"
GRADE = "grade"
REWRITE = "rewrite"
GENERATE = "generate"


class SearchState(TypedDict, total=False):
    """编排图的状态。

    ``matches`` 里放的是 MatchResult ORM 对象（内存图，不序列化），
    最终由调用方转成响应 dict。
    """

    goal: str
    job_id: str
    raw_text: str
    requirements: dict
    attempt: int
    max_attempts: int
    matches: list[Any]
    grade: dict
    rewritten: bool
    summary: str
    trace: list[dict]


def decide_after_rewrite(state: SearchState) -> str:
    """改写为空就不必再查一次。

    如果改写节点没有产出任何变化（常见于"这个岗位语料里根本不存在"），
    再检索一遍必然得到完全相同的结果——纯属浪费一次检索和一次模型调用。
    这种情况下直接收口，并把"试过但改不动"如实写进轨迹。
    """
    return RETRIEVE if state.get("rewritten") else GENERATE


def decide_next(state: SearchState) -> str:
    """纯函数：质量评估之后走哪条边。

    单独拆出来是为了能脱离图、脱离数据库做单元测试——这个决策恰恰是
    整个编排里唯一"智能"的部分，必须可以用普通断言锁住。

    **只有评估明确给出 ``weak`` 才允许重查**。评估缺失 / 异常 / 判不出，
    一律按单轮继续：没有证据就进入循环，图可能永远转下去。
    """
    grade = state.get("grade") or {}
    if grade.get("verdict") != "weak":
        return GENERATE
    if state.get("attempt", 0) >= state.get("max_attempts", MAX_ATTEMPTS):
        return GENERATE
    return REWRITE


class RecruitmentGraph:
    """把现有的解析 / 检索 / 评估 / 改写 / 生成封装成一张可执行的状态图。

    刻意不重写任何检索逻辑：每个节点都是对既有函数的调用。
    LangGraph 在这里只负责「状态流转 + 条件路由」，不负责业务。
    """

    def __init__(self, db: Session, job: JobRequirement, limit: int = 20):
        self.db = db
        self.job = job
        self.limit = limit
        self.settings = get_settings()

    # ------------------------------------------------------------------ 节点

    def _node_retrieve(self, state: SearchState) -> dict:
        attempt = state.get("attempt", 0) + 1
        requirements = JobRequirements.model_validate(state["requirements"])
        matches = search_job(
            self.db,
            self.job,
            self.limit,
            raw_text=state["raw_text"],
            requirements_override=requirements,
        )
        return {
            "matches": matches,
            "attempt": attempt,
            "trace": state.get("trace", []) + [{
                "node": RETRIEVE,
                "detail": f"第 {attempt} 次检索，召回 {len(matches)} 位候选人",
            }],
        }

    def _node_grade(self, state: SearchState) -> dict:
        service = ModelService(self.db)
        requirements = JobRequirements.model_validate(state["requirements"])
        grade = service.grade_recall(requirements, state.get("matches", []))
        return {
            "grade": grade,
            "trace": state.get("trace", []) + [{
                "node": GRADE,
                "verdict": grade.get("verdict"),
                "detail": "；".join(grade.get("reasons", [])[:2]) or f"评估结果：{grade.get('verdict')}",
            }],
        }

    def _node_rewrite(self, state: SearchState) -> dict:
        service = ModelService(self.db)
        requirements = JobRequirements.model_validate(state["requirements"])
        merged, new_text = service.rewrite_query(requirements, state.get("grade") or {}, state["raw_text"])
        changed = new_text != state["raw_text"] or merged != requirements
        return {
            "raw_text": new_text,
            "requirements": merged.model_dump(),
            "rewritten": changed,
            "trace": state.get("trace", []) + [{
                "node": REWRITE,
                "detail": "已改写并放宽部分条件，准备重查" if changed else "改写未产生有效变化，直接收口（避免用同样的查询白查一次）",
            }],
        }

    def _node_generate(self, state: SearchState) -> dict:
        requirements = JobRequirements.model_validate(state["requirements"])
        matches = state.get("matches", [])
        attempts = state.get("attempt", 1)
        summary = (
            f"我根据「{requirements.title}」整理了 {len(matches)} 位候选人。以下推荐均来自简历可核验内容。"
        )
        if attempts > 1:
            grade = state.get("grade") or {}
            reasons = "；".join((grade.get("reasons") or [])[:2])
            summary += f"（第 1 轮召回质量不佳{('：' + reasons) if reasons else ''}，已自动改写查询重查。）"
        return {
            "summary": summary,
            "trace": state.get("trace", []) + [{
                "node": GENERATE,
                "detail": f"生成推荐说明，共 {len(matches)} 位候选人",
            }],
        }

    # ------------------------------------------------------------------ 组装

    def build(self):
        from langgraph.graph import END, StateGraph

        graph = StateGraph(SearchState)
        graph.add_node(RETRIEVE, self._node_retrieve)
        graph.add_node(GRADE, self._node_grade)
        graph.add_node(REWRITE, self._node_rewrite)
        graph.add_node(GENERATE, self._node_generate)
        graph.set_entry_point(RETRIEVE)
        graph.add_edge(RETRIEVE, GRADE)
        graph.add_conditional_edges(GRADE, decide_next, {REWRITE: REWRITE, GENERATE: GENERATE})
        # 改写没改出东西就不必再查一遍
        graph.add_conditional_edges(REWRITE, decide_after_rewrite, {RETRIEVE: RETRIEVE, GENERATE: GENERATE})
        graph.add_edge(GENERATE, END)
        return graph.compile()

    def invoke(self) -> dict:
        initial: SearchState = {
            "goal": self.job.raw_text or "",
            "job_id": self.job.id,
            "raw_text": self.job.raw_text or "",
            "requirements": self.job.requirements_json or {},
            "attempt": 0,
            "max_attempts": MAX_ATTEMPTS,
            "matches": [],
            "grade": {},
            "rewritten": False,
            "summary": "",
            "trace": [],
        }
        final = self.build().invoke(initial)
        return {
            "matches": final.get("matches", []),
            "summary": final.get("summary", ""),
            "trace": final.get("trace", []),
            "attempts": final.get("attempt", 1),
        }


def run_orchestrated_search(db: Session, job: JobRequirement, limit: int = 20) -> dict:
    """入口。任何异常都退回单轮固定流水线，保证主链路永远可用。"""
    try:
        return RecruitmentGraph(db, job, limit).invoke()
    except Exception as exc:  # noqa: BLE001 - 编排失败绝不能拖垮检索
        print(f"[orchestration] 编排图执行失败，退回固定流水线：{exc}", flush=True)
        matches = search_job(db, job, limit)
        return {
            "matches": matches,
            "summary": f"我根据岗位条件整理了 {len(matches)} 位候选人。以下推荐均来自简历可核验内容。",
            "trace": [{"node": "fallback", "detail": f"编排图不可用，已退回固定流水线（{type(exc).__name__}）"}],
            "attempts": 1,
        }
