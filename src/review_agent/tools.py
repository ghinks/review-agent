import os
import urllib.request
from github import Github, Auth


DEFAULT_GITHUB_TIMEOUT = 30


def get_github_client(timeout: int = DEFAULT_GITHUB_TIMEOUT) -> Github:
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        auth = Auth.Token(token)
        return Github(auth=auth, timeout=timeout)
    return Github(timeout=timeout)


def get_pr_diff(repo_name: str, pr_number: int, timeout: int = DEFAULT_GITHUB_TIMEOUT) -> str:
    """Fetches the raw diff of a Pull Request."""
    token = os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3.diff")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        return f"Error fetching diff: {e}"


def get_pr_comments(repo_name: str, pr_number: int, timeout: int = DEFAULT_GITHUB_TIMEOUT) -> str:
    """Fetches the review comments and issue comments for a PR."""
    try:
        gh = get_github_client(timeout=timeout)
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        output = []
        output.append(f"PR Title: {pr.title}")
        output.append(f"PR Body: {pr.body or ''}")
        
        # Issue comments (general PR comments)
        issue_comments = pr.get_issue_comments()
        if issue_comments.totalCount > 0:
            output.append("\n--- General Comments ---")
            for comment in issue_comments:
                output.append(f"[{comment.user.login}]: {comment.body}")
                
        # Review comments (inline code comments)
        review_comments = pr.get_review_comments()
        if review_comments.totalCount > 0:
            output.append("\n--- Review Comments ---")
            for r_comment in review_comments:
                output.append(f"[{r_comment.user.login}] on {r_comment.path}:{r_comment.original_line}: {r_comment.body}")
                
        return "\n".join(output)
    except Exception as e:
        return f"Error fetching comments: {e}"
