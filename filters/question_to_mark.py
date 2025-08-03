import re

def process(input: str) -> str:
    return re.sub(r"[Qq]uestion([\.!]*)$", "\\1?", input)