import re


def content_warnings(content: str, *, collected: bool = True) -> list[str]:
    """Hints only; absence of a marker is never proof of a complete article."""
    text = content.strip()
    warnings: list[str] = []
    if not text:
        warnings.append("正文为空，请先补充资料。")
    elif re.search(r"\[\s*(?:\.{3}|…+)\s*\]|(?:阅读|查看)全文|继续阅读|read\s+more", text[-500:], re.I):
        warnings.append("疑似摘要：末尾含省略或阅读全文标记，AI 只能使用当前片段。")
    elif collected and len(text) < 600:
        warnings.append("当前内容较短，可能只有摘要；生成前请对照原文确认。")
    if collected and len(text) >= 10000:
        warnings.append("订阅采集有 10,000 字符上限，当前正文可能被截断。")
    return warnings
