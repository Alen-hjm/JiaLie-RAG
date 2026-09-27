from app.services.privacy import mask_email, mask_id_card, mask_phone, mask_pii
from app.services.search import _clip, _mask


def test_phone_keeps_prefix_and_suffix():
    """保留前 3 后 4：招聘方常要靠后四位跟候选人核对身份，全遮蔽反而不可用。"""
    assert mask_phone("13800000001") == "138****0001"
    assert mask_phone("联系方式：13800000001（微信同号）") == "联系方式：138****0001（微信同号）"


def test_email_hides_local_part_but_keeps_domain():
    """域名保留 —— @company.com 本身是有价值的招聘信号。"""
    assert mask_email("lin.demo@example.com") == "l***@example.com"
    assert mask_email("a@b.cn") == "a***@b.cn"


def test_id_card_is_masked():
    assert mask_id_card("110101199001011234") == "110101********1234"


def test_phone_rule_does_not_eat_id_card_digits():
    """18 位身份证不能被手机号规则切走中间 11 位。"""
    masked = mask_pii("110101199001011234")
    assert masked == "110101********1234"


def test_business_numbers_are_left_alone():
    """业绩数字不能误伤 —— 打错会让候选人看起来像信息损坏。"""
    text = "2024 年销售额 1.2 亿元，同比增长 36%，团队 18 人"
    assert mask_pii(text) == text


def test_mask_pii_handles_all_three_types_in_one_pass():
    text = "张三 13800000001 zhangsan@company.cn 110101199001011234"
    masked = mask_pii(text)
    assert "13800000001" not in masked
    assert "zhangsan@" not in masked
    assert "19900101" not in masked
    # 姓名必须保留：它是招聘流程的核心字段
    assert "张三" in masked


def test_clip_truncates_and_masks_together():
    text = "电话 13800000001 " + "长" * 500
    clipped = _clip(text, 20, True)
    assert len(clipped) == 20
    assert "13800000001" not in clipped


def test_mask_switch_can_be_turned_off():
    """保留一个"原样输出"的口子，便于排查"脱敏是不是把数据弄坏了"。"""
    text = "电话 13800000001"
    assert "13800000001" in _mask(text, False)
    assert "13800000001" not in _mask(text, True)
