import re

TOKENS = [
    r"\{\{[^}]+\}\}",
    r"\{[a-zA-Z0-9_]+\}",
    r"%\d+\$s",
    r"%s",
    r"%d",
    r"%f",
    r":[a-zA-Z_]\w*",
    r"\$[A-Z_]+",
    r"<\/?[0-9a-zA-Z]+[^>]*>",
    r"\{[^{}]*,\s*(plural|select)[^{}]*\{[^{}]*\}[^{}]*\}",
]
RE = re.compile("|".join(TOKENS))


def protect(s):
    mapping = {}

    def sub(m):
        k = f"__PH_{len(mapping)}__"
        mapping[k] = m.group(0)
        return k

    return RE.sub(sub, s), mapping


def unprotect(s, mapping):
    for k, v in mapping.items():
        s = s.replace(k, v)
    return s
