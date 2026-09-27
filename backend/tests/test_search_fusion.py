"""检索召回层的单元测试。

覆盖本次新增/改造的部分：
  - RRF 融合（把"两路都命中"排在"只命中一路"之前）
  - 关键词查询词的构造（单字噪声过滤、去重、上限）
  - 余弦相似度在维度不一致时必须返回 0，而不是算出一个看似合理的错值
  - 评测脚本的分级 NDCG / Recall / MRR
"""

from app.services.search import _query_terms, _rrf_fuse
from app.services.vectors import cosine
from app.schemas import JobRequirements
from scripts.evaluate import ndcg_at_k, recall_at_k, reciprocal_rank


def test_rrf_fusion_prefers_documents_hit_by_both_lanes():
    vector_lane = ["a", "b", "c"]
    keyword_lane = ["c", "d"]
    fused = _rrf_fuse([vector_lane, keyword_lane])
    # "c" 同时出现在两路，应当排在只出现一路的 a/b/d 之前
    assert fused[0] == "c"
    assert set(fused) == {"a", "b", "c", "d"}


def test_rrf_fusion_handles_empty_lane():
    assert _rrf_fuse([[], ["x", "y"]]) == ["x", "y"]
    assert _rrf_fuse([[], []]) == []


def test_query_terms_drops_single_char_noise_and_dedupes():
    job = JobRequirements(
        title="销售经理",
        industries=["半导体", "半导体"],
        locations=["上海"],
        skills=["大客户"],
        must_have=["具备半导体行业经验"],
    )
    terms = _query_terms(job)
    assert "半导体" in terms
    assert "销售经理" in terms
    assert "上海" in terms          # 两字保留
    assert len(terms) == len(set(terms))  # 去重
    assert all(len(term) >= 2 for term in terms)


def test_cosine_returns_zero_on_dimension_mismatch():
    # 维度不一致时不能"算出一个数"：旧的 zip() 写法会静默截断，得到看似合理的错值
    assert cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0
    assert cosine([], [1.0]) == 0.0
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_recall_at_k():
    ranked = ["a", "b", "c", "d"]
    relevant = {"c", "d", "z"}
    assert recall_at_k(ranked, relevant, 2) == 0.0
    assert recall_at_k(ranked, relevant, 4) == 2 / 3
    assert recall_at_k(ranked, set(), 4) == 1.0  # 没有相关项时不惩罚


def test_reciprocal_rank():
    assert reciprocal_rank(["x", "a", "b"], {"a"}) == 0.5
    assert reciprocal_rank(["a", "b"], {"a"}) == 1.0
    assert reciprocal_rank(["b"], {"a"}) == 0.0


def test_ndcg_uses_graded_relevance():
    # 理想排序是 grade 3 在首位
    ideal = [3, 2, 1]
    assert ndcg_at_k([3, 2, 1], ideal, 3) == 1.0
    # 把 grade 3 排到最后，得分必须显著下降
    assert ndcg_at_k([1, 2, 3], ideal, 3) < 1.0
    # 未标注的候选人 grade 记为 0，排在前面会拉低分数
    assert ndcg_at_k([0, 3], ideal, 2) < ndcg_at_k([3, 0], ideal, 2)
