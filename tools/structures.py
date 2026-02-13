"""Utility helpers for working with nested locale structures."""

from __future__ import annotations

from typing import Any, Iterator, Tuple, Union

PathType = Tuple[Union[str, int], ...]


def iter_string_nodes(obj: Any, path: PathType = ()) -> Iterator[Tuple[PathType, str]]:
    """Yield paths to every string leaf inside a nested mapping/list."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from iter_string_nodes(value, path + (key,))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from iter_string_nodes(value, path + (index,))
    elif isinstance(obj, str):
        yield path, obj


def get_value(obj: Any, path: PathType) -> Any:
    """Safely read a value from a nested mapping/list using the provided path."""
    current = obj
    for part in path:
        if isinstance(part, int):
            if isinstance(current, list) and 0 <= part < len(current):
                current = current[part]
            else:
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def set_value(obj: Any, path: PathType, value: Any) -> None:
    """Set a value inside a nested mapping/list using the provided path."""
    if not path:
        raise ValueError("Path must not be empty")
    current = obj
    for part in path[:-1]:
        if isinstance(part, int):
            current = current[part]
        else:
            current = current[part]
    last = path[-1]
    if isinstance(last, int):
        current[last] = value
    else:
        current[last] = value


def path_to_key(path: PathType) -> str:
    """Convert a path tuple into a stable string key used for translation."""
    if not path:
        return ""
    parts: list[str] = []
    for part in path:
        if isinstance(part, int):
            if not parts:
                parts.append(f"[{part}]")
            else:
                parts[-1] = f"{parts[-1]}[{part}]"
        else:
            parts.append(str(part))
    return ".".join(parts)


__all__ = ["PathType", "iter_string_nodes", "get_value", "set_value", "path_to_key"]
