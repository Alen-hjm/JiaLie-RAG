from app.schemas import JobRequirements
from app.services.search import _query_terms
from app.services.synonyms import expand_terms, variants_of


def test_fab_expands_to_chinese_equivalent():
    """PRD 点名的场景：JD 写「Fab 客户」，简历写「晶圆厂客户」。"""
    variants = [item.lower() for item in variants_of("fab")]
    assert "晶圆厂" in variants
    assert "foundry" in variants


def test_expansion_is_bidirectional():
    """反向也要通：JD 写中文，简历写英文。"""
    assert "fab" in [item.lower() for item in variants_of("晶圆厂")]


def test_short_latin_acronym_does_not_match_inside_longer_words():
    """`ic` 不能命中 logistics，否则词表反而污染召回的精确性。"""
    assert variants_of("logistics") == ["logistics"]
    assert variants_of("marketing") == ["marketing"]


def test_phrase_containing_alias_still_expands():
    """「Fab 客户开发」这类短语应命中 fab 组，而不是整条当陌生词丢掉。"""
    assert "晶圆厂" in variants_of("Fab 客户开发")


def test_expand_terms_dedupes_and_keeps_original_first():
    terms = expand_terms(["晶圆厂", "fab"])
    assert terms[0] == "晶圆厂"
    lowered = [item.lower() for item in terms]
    assert len(lowered) == len(set(lowered))


def test_expand_terms_respects_limit():
    terms = expand_terms(["fab", "大客户经理", "bd", "crm", "erp", "新能源"], limit=6)
    assert len(terms) == 6


def test_query_terms_expansion_is_switchable():
    """开关必须真的有效——这是 `--baseline` 对照实验成立的前提。"""
    job = JobRequirements(
        title="半导体销售总监",
        industries=["半导体"],
        skills=["Fab 客户开发"],
        locations=["上海"],
    )
    expanded = _query_terms(job, expand=True)
    plain = _query_terms(job, expand=False)

    assert len(expanded) > len(plain)
    assert "晶圆厂" in expanded
    assert "晶圆厂" not in plain
    # 原词一个都不能丢：扩展是补充，不是替换
    assert set(plain).issubset(set(expanded))


def test_unknown_term_passes_through_unchanged():
    assert expand_terms(["完全不存在的自定义词zzz"]) == ["完全不存在的自定义词zzz"]
