import itertools
import re


def infer_intent(key, value):
    k = key.lower()
    if re.search(r"(button|btn|cta|action|submit|next|prev)$", k):
        return "button"
    if re.search(r"(title|header|headline|modal_title)$", k):
        return "title"
    if re.search(r"(error|validation|failed|required)", k):
        return "error"
    if re.search(r"(label|placeholder|hint)$", k):
        return "label"
    if re.search(r"(tooltip|helper|description)$", k):
        return "tooltip"
    return "text"


def chunked(seq, n):
    it = iter(seq)
    while True:
        chunk = list(itertools.islice(it, n))
        if not chunk:
            break
        yield chunk
