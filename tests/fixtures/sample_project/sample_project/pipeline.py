from sample_project.calculator import add
from sample_project.formatter import title


def summarize(name: str, value: int) -> str:
    return f"{title(name)}: {add(value, 1)}"
