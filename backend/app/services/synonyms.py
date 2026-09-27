"""招聘领域的同义词 / 别名词典。

## 为什么要这个

PRD 里点名的第一个痛点：「简历写『晶圆厂客户』，JD 写『Fab 客户』，关键词检索
直接漏人」。向量路能补一部分语义，但中文招聘语料里混着大量英文缩写和行业黑话，
而向量召回在两种情况下并不可靠：

  1. 降级场景（``EMBEDDING_MODE=hash``）下向量本身是哈希占位，没有语义；
  2. 即便是真向量，"Fab" 和 "晶圆厂" 这种**符号级**的对应关系，
     在中文语料上召回也并不总是稳。

关键词路的存在意义正是「补向量漏掉的精确匹配」。但**精确匹配要求两边写法一致**，
所以关键词路必须有同义词表，否则它只能匹配到字面完全相同的词——
那恰恰是向量路本来就能搞定的部分，等于白留一条路。

## 设计取舍

1. **只扩展检索词，不改写 JD 本身。** 用户看到的需求描述必须是他自己说的那句话，
   系统不能偷偷往里面塞词。扩展只发生在召回层。
2. **不打分。** 同义词只影响"能不能被捞出来"，最终排序仍由结构化分 + 语义分 +
   重排分决定。这样即使词表有噪声，也只会让排名靠后的人进入候选池，
   不会让不该上榜的人排到前面。
3. **词表刻意保持小。** 只收"真实会写进简历和 JD 的行业叫法"。
   词表越大，召回噪声越多，而噪声要靠后续排序层去消化——不划算。
4. **双向扩展。** 命中组内任一写法，就把该组所有写法都加进检索词。
   简历不可能和 JD 用同一套词，所以扩展必须是双向的。
"""

from __future__ import annotations

import re

__all__ = ["SYNONYM_GROUPS", "expand_terms", "variants_of"]

# 同义词组。同组内的写法被认为在招聘语境下指向同一件事。
# 加词前的自问：这个词真的会出现在**简历或 JD 正文**里吗？
SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    # ---------------- 半导体 / 集成电路 ----------------
    ("fab", "晶圆厂", "晶圆代工", "foundry", "wafer fab"),
    ("ic", "集成电路", "芯片", "半导体", "chip"),
    ("封测", "封装测试", "osat"),
    # ---------------- 新能源 / 汽车 ----------------
    ("新能源", "锂电", "锂电池", "光伏", "储能"),
    ("oem", "整车厂", "主机厂", "车厂"),
    ("tier1", "一级供应商", "tier 1"),
    # ---------------- 医疗健康 ----------------
    ("医疗器械", "医械", "医疗设备"),
    ("医药", "制药", "生物医药", "biotech"),
    # ---------------- 销售类职位 ----------------
    ("销售总监", "销售负责人", "sales director"),
    ("大客户经理", "ka", "key account", "大客户销售"),
    ("区域经理", "区域销售经理", "regional sales manager"),
    ("bd", "商务拓展", "business development", "商务经理"),
    ("售前", "解决方案", "presales", "pre-sales"),
    ("售后", "客户成功", "customer success"),
    ("渠道", "渠道管理", "经销商", "channel"),
    # ---------------- 技术类职位 ----------------
    ("后端", "服务端", "backend"),
    ("前端", "frontend", "web 前端"),
    ("全栈", "full stack", "fullstack"),
    ("算法工程师", "机器学习工程师", "ai 工程师"),
    ("测试工程师", "qa", "质量保证"),
    ("运维", "sre", "devops"),
    # ---------------- 通用业务词 ----------------
    ("crm", "客户关系管理"),
    ("erp", "企业资源计划"),
    ("团队管理", "带团队", "管理经验"),
)

# 英文缩写（ic / ka / bd / qa / crm / erp…）如果按子串匹配，
# "ic" 会命中 "logistics"、"ka" 会命中 "marketing"，噪音极大。
# 所以含英文字母的候选词一律按词边界匹配，中文才允许子串匹配。
_HAS_LATIN = re.compile(r"[a-z]", re.IGNORECASE)


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _occurrences(haystack: str, needle: str) -> bool:
    """needle 是否作为"一个词"出现在 haystack 里。"""
    if not haystack or not needle:
        return False
    if _HAS_LATIN.search(needle):
        # 前后不能紧跟字母或数字，避免 ic 命中 logistics
        pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
        return re.search(pattern, haystack, re.IGNORECASE) is not None
    return needle in haystack


def variants_of(term: str) -> list[str]:
    """返回该词的同义写法。**原词始终排在第一位**；没有命中任何组时返回 ``[term]``。

    原词必须保留：扩展是"补充召回面"，不是"把用户说过的话换掉"。
    早期版本在这里直接把整条短语替换成组内写法，结果「Fab 客户开发」被换成了
    「晶圆厂」——限定词「客户开发」消失，召回反而变宽变糊。测试把这个漏洞抓了出来
    （见 tests/test_synonyms.py 里对 issubset 的断言）。
    """
    normalized = _normalize(term)
    if not normalized:
        return []
    for group in SYNONYM_GROUPS:
        lower_group = [_normalize(item) for item in group]
        # 精确命中整组；或长短语里含有组内某个词（如「Fab 客户开发」含「fab」）
        if normalized in lower_group or any(_occurrences(normalized, item) for item in lower_group):
            return [term, *group]
    return [term]


def expand_terms(terms: list[str], limit: int = 48) -> list[str]:
    """把检索词按同义词组扩展，原词始终排在前面。

    ``limit`` 是硬上限：关键词路是 ``OR`` 条件，词越多召回面越宽、噪声也越多。
    48 是经验值——够覆盖一整个 JD 的行业词 + 技能词扩展，又不会把
    "任一带『管理』二字的简历"全捞进来。
    """
    out: list[str] = []
    seen: set[str] = set()
    for term in terms:
        for variant in variants_of(term):
            key = _normalize(variant)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(variant.strip())
            if len(out) >= limit:
                return out
    return out
