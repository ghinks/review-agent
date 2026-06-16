import pytest

from review_agent.pr_sources import (
    MANUAL_REASON,
    load_pr_numbers_from_file,
    manual_pr_record,
    merge_records,
    parse_pr_numbers,
)

REPO = "owner/repo"


def test_parse_one_per_line():
    assert parse_pr_numbers("1\n2\n3\n") == [1, 2, 3]


def test_parse_ignores_blank_lines():
    assert parse_pr_numbers("\n1\n\n  \n2\n") == [1, 2]


def test_parse_strips_hash_prefix():
    assert parse_pr_numbers("#10\n#20\n") == [10, 20]


def test_parse_comma_and_space_separated():
    assert parse_pr_numbers("1, 2 3\n4,5") == [1, 2, 3, 4, 5]


def test_parse_invalid_raises_with_line_number():
    with pytest.raises(ValueError, match="line 2"):
        parse_pr_numbers("1\nnope\n3")


def test_load_from_file(tmp_path):
    f = tmp_path / "prs.txt"
    f.write_text("#100\n101\n")
    assert load_pr_numbers_from_file(str(f)) == [100, 101]


def test_manual_pr_record_shape():
    record = manual_pr_record(REPO, 42)
    assert record["number"] == 42
    assert record["url"] == "https://github.com/owner/repo/pull/42"
    assert record["outlier_features"] == MANUAL_REASON
    assert record["max_abs_z_score"] is None


def test_merge_appends_manual_numbers():
    db = [{"number": 1, "outlier_features": "additions", "max_abs_z_score": 3.0}]
    merged = merge_records(db, [2, 3], REPO)
    assert [r["number"] for r in merged] == [1, 2, 3]
    assert merged[1]["outlier_features"] == MANUAL_REASON


def test_merge_dedupes_db_takes_precedence():
    db = [{"number": 1, "outlier_features": "additions", "max_abs_z_score": 3.0}]
    merged = merge_records(db, [1, 2], REPO)
    assert [r["number"] for r in merged] == [1, 2]
    # The PR already present from the DB keeps its statistical metadata.
    assert merged[0]["max_abs_z_score"] == 3.0


def test_merge_preserves_manual_order_and_dedupes_within_manual():
    merged = merge_records([], [5, 5, 9, 5], REPO)
    assert [r["number"] for r in merged] == [5, 9]
