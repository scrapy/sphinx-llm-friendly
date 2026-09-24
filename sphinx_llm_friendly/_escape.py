import re

# Backslashes, asterisks, backticks, and underscores at the start of a line or
# word.
_ESCAPE_RE = re.compile(r"([\\*`]|(?:^|(?<=\s|_))_)", re.MULTILINE)


def escape_markdown_chars(txt: str) -> str:
    return _ESCAPE_RE.sub(r"\\\1", txt)


def escape_html_quote(value: str) -> str:
    return value.replace('"', "&quot;")
