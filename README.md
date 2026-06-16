# review-agent

Agentic analysis of pull-request outliers.

## Overview

`review-agent` is a command-line tool that explains **why** a pull request was
statistically flagged as an outlier. It reads pre-computed outlier PRs from a SQLite
database, then hands each one to an LLM agent. The agent uses GitHub tools to fetch the
PR diff and review comments, reasons about the anomaly (a difficult refactor? a
controversial architectural change? a long review?), and the results are written to a
single Markdown report.

The reasoning backend is pluggable — choose one with `--sdk`:

| `--sdk`        | SDK                                                                                     | Model            |
| -------------- | --------------------------------------------------------------------------------------- | ---------------- |
| `antigravity`  | [`google-antigravity`](https://github.com/google-antigravity/antigravity-sdk-python)    | `gemini-2.5-pro` |
| `openai`       | [`openai`](https://github.com/openai/openai-python)                                      | `gpt-5`          |
| `anthropic`    | [`anthropic`](https://github.com/anthropics/anthropic-sdk-python)                        | `claude-opus-4-8`|

`antigravity` (Gemini) is the default. Each backend lives in its own folder under
`src/review_agent/providers/`.

See [`agentic_report.md`](agentic_report.md) for a sample of the generated output.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** for dependency management and running the tool
- A **`review_classification.db`** SQLite database produced upstream, containing the
  `pullrequest` and `proutlierscore` tables (PRs are selected where
  `proutlierscore.is_outlier = 1`)
- A **GitHub token** (`GITHUB_TOKEN`) — recommended to avoid API rate limits and to
  access private repositories
- An **API key for the SDK you select** — only the key for the chosen `--sdk` is needed
  at runtime:
  - `--sdk antigravity` (default) → `GEMINI_API_KEY`
  - `--sdk openai` → `OPENAI_API_KEY`
  - `--sdk anthropic` → `ANTHROPIC_API_KEY`

## Installation

Install all dependencies (including the git-sourced `google-antigravity` SDK) with:

```bash
uv sync
```

This creates a virtual environment and installs the `review-agent` console script.

## Configuration

Export the API key for your chosen SDK plus a GitHub token before running. For the
default (`antigravity`/Gemini):

```bash
export GEMINI_API_KEY=your_gemini_api_key_here   # or OPENAI_API_KEY / ANTHROPIC_API_KEY
export GITHUB_TOKEN=ghp_your_token_here
```

The SDK reads its key from the environment to authenticate against the model — only the
key for the SDK passed to `--sdk` is required (`GEMINI_API_KEY` for `antigravity`,
`OPENAI_API_KEY` for `openai`, `ANTHROPIC_API_KEY` for `anthropic`). `GITHUB_TOKEN` is
optional but strongly recommended to avoid API rate limits and to access private
repositories.

## Usage

Analyze the outlier PRs from the database:

```bash
uv run review-agent \
  --db-path ./review_classification.db \
  --repo expressjs/express
```

PRs can come from any combination of three sources: the outlier database
(`--db-path`), specific PR numbers (`--pr`, repeatable), and/or a file of PR
numbers (`--pr-file`). At least one source is required. Analyze specific PRs
without touching the database:

```bash
uv run review-agent \
  --repo expressjs/express \
  --pr 1234 --pr 1240 \
  --pr-file ./prs.txt
```

The `--pr-file` lists one PR number per line (a leading `#` and comma/space
separated values are also accepted). Sources are merged and deduplicated by PR
number; database records keep their statistical metadata.

Pick a different reasoning SDK, write to a custom output file, and limit how many PRs
are analyzed:

```bash
uv run review-agent \
  --db-path ./review_classification.db \
  --repo expressjs/express \
  --sdk anthropic \
  --output express_report.md \
  --limit 5
```

### Options

| Option        | Required | Default              | Description                                                          |
| ------------- | -------- | -------------------- | ------------------------------------------------------------------- |
| `--repo`      | yes      | —                    | GitHub repository as `owner/repo`                                   |
| `--db-path`   | no\*     | —                    | Path to the `review_classification.db` SQLite file (outlier PRs)    |
| `--pr`        | no\*     | —                    | A specific PR number to analyze; repeat to add more                 |
| `--pr-file`   | no\*     | —                    | Path to a file listing PR numbers to analyze                        |
| `--from-date` | no       | (all)                | Only analyze DB outlier PRs created on/after midnight of `YYYY-MM-DD` |
| `--sdk`       | no       | `antigravity`        | Reasoning SDK: `antigravity` \| `openai` \| `anthropic`             |
| `--output`    | no       | `agentic_report.md`  | Output Markdown file                                                |
| `--limit`     | no       | (all)                | Maximum number of PRs to analyze                                    |

\* At least one of `--db-path`, `--pr`, or `--pr-file` is required.

See all options with:

```bash
uv run review-agent --help
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
├── main.py        # Typer CLI; the `analyze` command and per-PR orchestration
├── db.py          # get_outliers(): loads outlier PRs from the SQLite database
├── pr_sources.py  # Loads PR numbers from --pr / --pr-file and merges with DB records
├── tools.py       # SDK-agnostic GitHub tools: get_pr_diff() and get_pr_comments()
├── prompts.py     # Shared system instructions and per-PR prompt builder
└── providers/     # Pluggable reasoning backends (one folder per SDK)
    ├── base.py        # AgentProvider protocol + Sdk enum
    ├── __init__.py    # get_provider() factory (lazy per-SDK imports)
    ├── antigravity/   # Gemini via google-antigravity (agent.chat loop)
    ├── openai/        # GPT via the OpenAI Responses API (manual tool loop)
    └── anthropic/     # Claude via the Anthropic Messages API (manual tool loop)
```
