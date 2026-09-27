"""上传文件名编码的回归测试。

浏览器在 multipart 的 ``filename=`` 里直接放 UTF-8 原始字节，而 Starlette 的
multipart 解析器按 latin-1 解码该字段，于是中文简历名会变成乱码
（``½¯×Óºã_°ëµ¼ÌåÏúÊÛ×Ü¼à.docx``）。``normalize_filename`` 负责把它还原。
"""

from app.routers.resumes import normalize_filename


def _as_browser_sends(name: str) -> str:
    """模拟 Starlette 的行为：拿到 UTF-8 字节后按 latin-1 解码。"""
    return name.encode("utf-8").decode("latin-1")


def test_repairs_mojibake_chinese_filename():
    original = "林若川_半导体销售总监.docx"
    garbled = _as_browser_sends(original)
    assert garbled != original  # 先确认这确实是乱码
    assert normalize_filename(garbled, ".docx") == original


def test_keeps_ascii_filename_untouched():
    assert normalize_filename("resume_john_doe.pdf", ".pdf") == "resume_john_doe.pdf"


def test_falls_back_when_filename_missing():
    assert normalize_filename(None, ".docx") == "resume.docx"
    assert normalize_filename("", ".pdf") == "resume.pdf"


def test_unrepairable_bytes_are_returned_as_is():
    # 系统 ANSI（GBK）字节流无法通过 latin-1 -> utf-8 还原，此时原样返回而不是抛错
    gbk_garbled = "范文启.docx".encode("gbk").decode("latin-1")
    assert normalize_filename(gbk_garbled, ".docx") == gbk_garbled
