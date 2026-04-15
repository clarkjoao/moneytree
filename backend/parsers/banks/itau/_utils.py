from __future__ import annotations

from collections.abc import Mapping

_LINE_TOP_TOLERANCE = 3.0


def _group_words_by_line(
    words: list[Mapping[str, float | str]],
    tolerance: float = _LINE_TOP_TOLERANCE,
) -> dict[float, list[Mapping[str, float | str]]]:
    """
    Group words by vertical position (`top`) using tolerance.

    Returns a mapping where each key is a representative `top` value and
    each value is the words from that line sorted by `x0`.
    """
    lines: dict[float, list[Mapping[str, float | str]]] = {}

    for word in words:
        top_value = float(word["top"])
        matched_top: float | None = None
        for existing_top in lines:
            if abs(existing_top - top_value) <= tolerance:
                matched_top = existing_top
                break
        line_key = matched_top if matched_top is not None else top_value
        lines.setdefault(line_key, []).append(word)

    return {
        top_value: sorted(line_words, key=lambda item: float(item["x0"]))
        for top_value, line_words in lines.items()
    }
