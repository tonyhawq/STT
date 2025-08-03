import re

def process(input: str) -> str:
    return re.sub("[\\.!]+$", "!!!", input)