from types import SimpleNamespace
from app.schemas import JobRequirements
from app.services.search import structured_score, cosine
from app.services.llm import mock_candidate


def test_structured_score_rewards_relevant_candidate():
    job = JobRequirements(title="销售总监", industries=["半导体"], locations=["上海"], minimum_years=8, skills=["大客户"], management_required=True)
    relevant = SimpleNamespace(industries=["半导体"], location="上海", years_experience=10, skills=["大客户"], management_experience=True)
    unrelated = SimpleNamespace(industries=["互联网"], location="北京", years_experience=3, skills=[], management_experience=False)
    assert structured_score(job, relevant) == 1
    assert structured_score(job, unrelated) < 0.2


def test_cosine_similarity():
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1, 0], [0, 1]) == 0


def test_resume_year_does_not_treat_calendar_year_as_experience():
    candidate = mock_candidate("林若川\n12 年半导体销售经验\n2024 年销售额 1.2 亿元")
    assert candidate.years_experience == 12
