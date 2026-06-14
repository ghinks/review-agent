# review-agent

Agentic analysis of pull-request outliers.

## Overview

`review-agent` is a command-line tool that explains **why** a pull request was
statistically flagged as an outlier. It reads pre-computed outlier PRs from a SQLite
database, then hands each one to an LLM agent (`gemini-2.5-pro` via the
[`google-antigravity`](https://github.com/google-antigravity/antigravity-sdk-python)
SDK). The agent uses GitHub tools to fetch the PR diff and review comments, reasons
about the anomaly (a difficult refactor? a controversial architectural change? a long
review?), and the results are written to a single Markdown report.

See [`agentic_report.md`](agentic_report.md) for a sample of the generated output.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** for dependency management and running the tool
- A **`review_classification.db`** SQLite database produced upstream, containing the
  `pullrequest` and `proutlierscore` tables (PRs are selected where
  `proutlierscore.is_outlier = 1`)
- A **GitHub token** (`GITHUB_TOKEN`) — recommended to avoid API rate limits and to
  access private repositories
- A **Gemini API key** (`GEMINI_API_KEY`) — **required** so the agent can reach the
  Gemini model via the `google-antigravity` SDK

## Installation

Install all dependencies (including the git-sourced `google-antigravity` SDK) with:

```bash
uv sync
```

This creates a virtual environment and installs the `review-agent` console script.

## Configuration

Export your Gemini API key and GitHub token before running:

```bash
export GEMINI_API_KEY=your_gemini_api_key_here
export GITHUB_TOKEN=ghp_your_token_here
```

`GEMINI_API_KEY` is **required** — the `google-antigravity` SDK reads it from the
environment to authenticate against the Gemini model. `GITHUB_TOKEN` is optional but
strongly recommended to avoid API rate limits and to access private repositories.

## Usage

Run the `analyze` command via `uv`:

```bash
uv run review-agent analyze \
  --db-path ./review_classification.db \
  --repo expressjs/express
```

Write to a custom output file and limit how many PRs are analyzed:

```bash
uv run review-agent analyze \
  --db-path ./review_classification.db \
  --repo expressjs/express \
  --output express_report.md \
  --limit 5
```

### Options

| Option       | Required | Default              | Description                                          |
| ------------ | -------- | -------------------- | ---------------------------------------------------- |
| `--db-path`  | yes      | —                    | Path to the `review_classification.db` SQLite file   |
| `--repo`     | yes      | —                    | GitHub repository as `owner/repo`                    |
| `--output`   | no       | `agentic_report.md`  | Output Markdown file                                 |
| `--limit`    | no       | (all)                | Maximum number of outlier PRs to analyze             |

See all options with:

```bash
uv run review-agent analyze --help
```

## Output

The tool writes a Markdown report (default `agentic_report.md`) with one section per
analyzed PR. Each section includes the PR number and title, the feature(s) that flagged
it as an outlier, its maximum absolute Z-score, and the agent's analysis of the anomaly
and any potential risks.

## Development

```bash
uv run pytest          # run tests
uv run ruff check      # lint
uv run mypy src        # type-check
```

## Project structure

```
src/review_agent/
├── main.py    # Typer CLI; the `analyze` command and agent orchestration
├── db.py      # get_outliers(): loads outlier PRs from the SQLite database
└── tools.py   # GitHub agent tools: get_pr_diff() and get_pr_comments()
```
