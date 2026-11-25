import re

def process(input: str) -> str:
    text = input

    # Replace common sounds
    replacements = [
        (r'[rl]', 'w'),
        (r'[RL]', 'W'),
        (r'n([aeiou])', r'ny\1'),
        (r'N([aeiou])', r'Ny\1'),
        (r'N([AEIOU])', r'NY\1'),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text