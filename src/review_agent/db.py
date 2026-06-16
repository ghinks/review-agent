import sqlite3
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Union


def _normalize_from_date(from_date: Union[str, date]) -> str:
    """Return a 'YYYY-MM-DD 00:00:00' threshold (midnight) for the given date.

    Accepts a ``date``/``datetime`` or an ISO ``YYYY-MM-DD`` string and raises
    ValueError on an unparseable string.
    """
    if isinstance(from_date, datetime):
        from_date = from_date.date()
    if isinstance(from_date, date):
        return f"{from_date.isoformat()} 00:00:00"
    # Validate the string is a real ISO date before using it in the query.
    parsed = date.fromisoformat(from_date)
    return f"{parsed.isoformat()} 00:00:00"


def get_outliers(
    db_path: str, repo: str, from_date: Optional[Union[str, date]] = None
) -> List[Dict[str, Any]]:
    """Fetch outlier PRs for a given repository from the review_classification DB.

    If ``from_date`` is provided, only PRs created on or after midnight of that
    date are returned.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT
        pr.number,
        pr.title,
        pr.author,
        pr.state,
        pr.url,
        pr.created_at,
        po.outlier_features,
        po.max_abs_z_score
    FROM pullrequest pr
    JOIN proutlierscore po ON pr.id = po.pull_request_id
    WHERE po.is_outlier = 1 AND pr.repository_name = ?
    """
    params: List[Any] = [repo]

    if from_date is not None:
        query += " AND pr.created_at >= ?"
        params.append(_normalize_from_date(from_date))

    query += " ORDER BY po.max_abs_z_score DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    outliers = [dict(row) for row in rows]
    conn.close()
    return outliers
