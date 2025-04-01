# TiDB PR MCP

A Model Control Protocol (MCP) tool for analyzing GitHub PRs in TiDB repositories. This tool provides functionality to check PR status, labels, details, and reviewers.

## Features

- Get PR status (open, closed, or merged)
- Retrieve PR labels
- Get detailed PR information (author, commits, changed files)
- Identify required reviewers or approvers and approval status

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package and project manager)
- GitHub API token (for higher rate limits)

## Installation

This project uses `uv` for package management. If you don't have `uv` installed, you can install it following the [official installation guide](https://github.com/astral-sh/uv?tab=readme-ov-file#installation).

1. Clone the repository:
   ```bash
   git clone https://github.com/wuhuizuo/caffeine-overflow
   cd tidb-pr-mcp
   ```

2. Install dependencies using uv:
   ```bash
   uv venv
   uv pip sync
   ```

3. Set up your GitHub token as an environment variable:
   ```bash
   export GITHUB_TOKEN="your-github-token"
   ```

## Usage

You can run the tool in two transport modes:

1. Standard I/O mode (default):
   ```bash
   uv run src/main.py
   ```

2. Server-Sent Events (SSE) mode:
   ```bash
   # Run the tool in SSE mode, default port is 8000
   # You can change the port by setting the MCP_PORT environment variable
   uv run src/main.py --sse
   ```

## Cursor IDE Integration

To use this MCP with Cursor IDE:

1. Open Cursor IDE settings
2. Navigate to the MCP section
3. Add a new MCP with the following configuration:
   - Name: TiDB PR Analyzer
   - Command: `uv run src/main.py`
   - Working Directory: `./tidb-pr-mcp`

4. Ensure your GITHUB_TOKEN is set in your environment or add it to the MCP configuration

## Available Tools

The MCP provides the following tools:

- `get_pr_status`: Check if a PR is open, closed, or merged
- `get_pr_labels`: Get all labels applied to a PR
- `get_pr_details`: Get detailed information about a PR
- `get_pr_reviewers`: Get information about required reviewers for a PR

## Example

In Cursor IDE, you can use the MCP with commands like:

```
Use the TiDB PR MCP to check the status of PR #9876
```


## License

[Apache License 2.0](LICENSE)
