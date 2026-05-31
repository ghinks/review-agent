import sqlite3
from typing import List, Dict, Any

def get_outliers(db_path: str, repo: str) -> List[Dict[str, Any]]:
    """Fetch outlier PRs for a given repository from the review_classification DB."""
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
        po.outlier_features,
        po.max_abs_z_score
    FROM pullrequest pr
    JOIN proutlierscore po ON pr.id = po.pull_request_id
    WHERE po.is_outlier = 1 AND pr.repository_name = ?
    ORDER BY po.max_abs_z_score DESC
    """
    
    cursor.execute(query, (repo,))
    rows = cursor.fetchall()
    
    outliers = [dict(row) for row in rows]
    conn.close()
    return outliers
