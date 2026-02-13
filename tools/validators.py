from collections import Counter
from typing import Dict, Iterable, List, Tuple

from tools.batcher import infer_intent
from tools.protect import RE as TOKEN_RE
from tools.structures import get_value, iter_string_nodes, path_to_key

KEY_DIFF_LIMIT = 20
TOKEN_DIFF_LIMIT = 5
CTA_MAX_WORDS = 4
CTA_TRAILING_PUNCT = (".", "?", ";", ",")
TITLE_PUNCTUATION = (".", "!", "?")


def check_keys(src: Dict[str, object], dst: Dict[str, object]) -> bool:
    """Ensure key sets match exactly."""
    src_keys = {path_to_key(path) for path, _ in iter_string_nodes(src)}
    dst_keys = {path_to_key(path) for path, _ in iter_string_nodes(dst)}
    missing = sorted(src_keys - dst_keys)
    extra = sorted(dst_keys - src_keys)
    if not missing and not extra:
        return True

    if missing:
        sample = missing[:KEY_DIFF_LIMIT]
        print("[fail] Missing keys in target:")
        for key in sample:
            print(f"  - {key}")
        if len(missing) > KEY_DIFF_LIMIT:
            print(f"  …and {len(missing) - KEY_DIFF_LIMIT} more")

    if extra:
        sample = extra[:KEY_DIFF_LIMIT]
        print("[fail] Unexpected extra keys in target:")
        for key in sample:
            print(f"  - {key}")
        if len(extra) > KEY_DIFF_LIMIT:
            print(f"  …and {len(extra) - KEY_DIFF_LIMIT} more")
    return False


def _token_counts(value: str) -> Counter:
    return Counter(TOKEN_RE.findall(value or ""))


def _format_token_diffs(expected: Counter, actual: Counter) -> Iterable[str]:
    diffs = []
    for token, count in expected.items():
        delta = count - actual.get(token, 0)
        if delta > 0:
            diffs.append(f"missing {token} ×{delta}")
    for token, count in actual.items():
        delta = count - expected.get(token, 0)
        if delta > 0:
            diffs.append(f"unexpected {token} ×{delta}")
    return diffs[:TOKEN_DIFF_LIMIT]


def check_tokens(src: Dict[str, object], dst: Dict[str, object]) -> bool:
    """Verify that placeholder/token multiset matches for every string value."""
    ok = True
    for path, en_value in iter_string_nodes(src):
        key = path_to_key(path)
        ru_value = get_value(dst, path)
        if not isinstance(ru_value, str):
            print(f"[fail] {key}: expected string translation, got {type(ru_value).__name__}")
            ok = False
            continue
        expected = _token_counts(en_value)
        actual = _token_counts(ru_value)
        if expected != actual:
            details = ", ".join(_format_token_diffs(expected, actual))
            if not details:
                details = "token counts differ"
            print(f"[fail] {key}: placeholder mismatch ({details})")
            ok = False
    return ok


def check_intent_style(
    src: Dict[str, object], dst: Dict[str, object]
) -> Tuple[bool, Iterable[str]]:
    """Run lightweight tone/intent heuristics. Returns (ok, messages)."""
    messages: List[str] = []
    ok = True
    for path, en_value in iter_string_nodes(src):
        key = path_to_key(path)
        value = get_value(dst, path)
        base_ok, base_messages, normalized = _run_base_checks(key, value)
        messages.extend(base_messages)
        if not base_ok:
            ok = False
            continue
        intent = infer_intent(key, en_value)
        messages.extend(_intent_specific_messages(intent, key, normalized))
    return ok, messages


def _run_base_checks(key: str, value: object) -> Tuple[bool, List[str], str]:
    messages: List[str] = []
    if value is None:
        messages.append(f"[fail] {key}: translation missing")
        return False, messages, ""
    if not isinstance(value, str):
        messages.append(f"[fail] {key}: translation is {type(value).__name__}, expected string")
        return False, messages, ""
    normalized = value.strip()
    if not normalized:
        messages.append(f"[fail] {key}: translation is empty")
        return False, messages, ""
    return True, messages, normalized


def _intent_specific_messages(intent: str, key: str, ru_value: str) -> List[str]:
    if intent == "button":
        return _validate_button(key, ru_value)
    if intent == "title":
        return _validate_title(key, ru_value)
    if intent == "error":
        return _validate_error(key, ru_value)
    return []


def _validate_button(key: str, ru_value: str) -> List[str]:
    issues: List[str] = []
    word_count = len(ru_value.split())
    if word_count > CTA_MAX_WORDS:
        issues.append(f"[warn] {key}: CTA is {word_count} words → '{ru_value}'")
    if ru_value.endswith(CTA_TRAILING_PUNCT):
        issues.append(f"[warn] {key}: CTA ends with punctuation → '{ru_value}'")
    return issues


def _validate_title(key: str, ru_value: str) -> List[str]:
    issues: List[str] = []
    if ru_value[0].islower():
        issues.append(f"[warn] {key}: title starts with lowercase → '{ru_value}'")
    if ru_value.endswith(TITLE_PUNCTUATION):
        issues.append(f"[warn] {key}: title ends with sentence punctuation → '{ru_value}'")
    return issues


def _validate_error(key: str, ru_value: str) -> List[str]:
    if ru_value.endswith("!"):
        return [f"[warn] {key}: error message ends with '!' → '{ru_value}'"]
    return []
