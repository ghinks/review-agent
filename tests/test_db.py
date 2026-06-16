import sqlite3
from datetime import date, datetime

import pytest

from review_agent.db import _normalize_from_date, get_outliers

REPO = "owner/repo"


def _make_db(path: str) -> None:
    """Create a minimal review_classification DB with a few outlier PRs."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE pullrequest (
            id INTEGER PRIMARY KEY,
            repository_name VARCHAR NOT NULL,
            number INTEGER NOT NULL,
            title VARCHAR NOT NULL,
            author VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            state VARCHAR NOT NULL,
            url VARCHAR NOT NULL
        );
        CREATE TABLE proutlierscore (
            id INTEGER PRIMARY KEY,
            pull_request_id INTEGER NOT NULL,
            is_outlier BOOLEAN NOT NULL,
            outlier_features VARCHAR,
            max_abs_z_score FLOAT
        );
        """
    )
    prs = [
        # (id, number, created_at, is_outlier, max_z)
        (1, 101, "2026-01-10 09:00:00.000000", 1, 3.5),
        (2, 102, "2026-03-15 12:30:00.000000", 1, 5.0),
        (3, 103, "2026-03-15 00:00:00.000000", 1, 2.0),  # exactly midnight
        (4, 104, "2026-05-01 08:00:00.000000", 0, 1.0),  # not an outlier
    ]
    for pr_id, number, created_at, is_outlier, max_z in prs:
        conn.execute(
            "INSERT INTO pullrequest (id, repository_name, number, title, author, created_at, state, url)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pr_id, REPO, number, f"PR {number}", "alice", created_at, "merged", f"http://x/{number}"),
        )
        conn.execute(
            "INSERT INTO proutlierscore (id, pull_request_id, is_outlier, outlier_features, max_abs_z_score)"
            " VALUES (?, ?, ?, ?, ?)",
            (pr_id, pr_id, is_outlier, "additions", max_z),
        )
    conn.commit()
    conn.close()


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "review_classification.db")
    _make_db(path)
    return path


def test_get_outliers_returns_created_at(db_path):
    outliers = get_outliers(db_path, REPO)
    assert outliers, "expected outliers"
    assert all("created_at" in o for o in outliers)


def test_get_outliers_excludes_non_outliers(db_path):
    numbers = {o["number"] for o in get_outliers(db_path, REPO)}
    assert numbers == {101, 102, 103}


def test_get_outliers_ordered_by_z_score(db_path):
    numbers = [o["number"] for o in get_outliers(db_path, REPO)]
    assert numbers == [102, 101, 103]


def test_from_date_filters_earlier_prs(db_path):
    numbers = {o["number"] for o in get_outliers(db_path, REPO, from_date="2026-03-15")}
    # PR 101 (Jan) is excluded; the midnight PR 103 on the boundary is included.
    assert numbers == {102, 103}


def test_from_date_includes_midnight_boundary(db_path):
    numbers = {o["number"] for o in get_outliers(db_path, REPO, from_date="2026-03-15")}
    assert 103 in numbers


def test_from_date_accepts_date_object(db_path):
    numbers = {o["number"] for o in get_outliers(db_path, REPO, from_date=date(2026, 3, 15))}
    assert numbers == {102, 103}


def test_from_date_no_matches(db_path):
    assert get_outliers(db_path, REPO, from_date="2026-12-31") == []


def test_normalize_from_date_string():
    assert _normalize_from_date("2026-03-15") == "2026-03-15 00:00:00"


def test_normalize_from_date_date_and_datetime():
    assert _normalize_from_date(date(2026, 3, 15)) == "2026-03-15 00:00:00"
    assert _normalize_from_date(datetime(2026, 3, 15, 23, 59)) == "2026-03-15 00:00:00"


def test_normalize_from_date_invalid():
    with pytest.raises(ValueError):
        _normalize_from_date("not-a-date")
