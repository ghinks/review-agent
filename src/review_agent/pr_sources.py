"""Loading PR numbers from sources other than the outlier database.

Supports an explicit list of PR numbers (from the CLI) and a file listing PR
numbers. These are normalized into the same record shape that
``db.get_outliers`` returns so the analysis loop can treat every source the same.
"""

import re
from typing import Any, Dict, List

# Reason recorded for PRs the user selected by hand rather than via the
# statistical outlier analysis.
MANUAL_REASON = "manually selected for inspection (not a statistical outlier)"

_SEPARATORS = re.compile(r"[,\s]+")


def parse_pr_numbers(text: str) -> List[int]:
    """Parse PR numbers from free text.

    Numbers may be separated by newlines, commas, or whitespace, and may carry
    an optional leading ``#`` (e.g. ``#123``). Blank lines are ignored. Raises
    ValueError on any token that is not a PR number.
    """
    numbers: List[int] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        for token in _SEPARATORS.split(line):
            token = token.lstrip("#").strip()
            if not token:
                continue
            try:
                numbers.append(int(token))
            except ValueError as e:
                raise ValueError(
                    f"Invalid PR number on line {lineno}: {token!r}"
                ) from e
    return numbers


def load_pr_numbers_from_file(path: str) -> List[int]:
    """Read PR numbers from a file. See ``parse_pr_numbers`` for the format."""
    with open(path) as f:
        return parse_pr_numbers(f.read())


def manual_pr_record(repo: str, number: int) -> Dict[str, Any]:
    """Build a record for a hand-selected PR, matching ``get_outliers`` keys."""
    return {
        "number": number,
        "title": "(manually selected)",
        "author": "",
        "state": "",
        "url": f"https://github.com/{repo}/pull/{number}",
        "created_at": None,
        "outlier_features": MANUAL_REASON,
        "max_abs_z_score": None,
    }


def merge_records(
    db_records: List[Dict[str, Any]], manual_numbers: List[int], repo: str
) -> List[Dict[str, Any]]:
    """Combine DB outlier records with manually requested PR numbers.

    Deduplicated by PR number. DB records take precedence because they carry the
    statistical metadata; manual numbers not already present are appended as
    manual records, preserving their input order.
    """
    seen = {record["number"] for record in db_records}
    merged = list(db_records)
    for number in manual_numbers:
        if number in seen:
            continue
        seen.add(number)
        merged.append(manual_pr_record(repo, number))
    return merged
