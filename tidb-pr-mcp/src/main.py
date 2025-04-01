from typing import Any, Dict, List, Optional
import httpx
import os
from mcp.server.fastmcp import FastMCP
import argparse
import re
import logging

# Initialize FastMCP server
mcp = FastMCP("github_pr_analyzer")

# Constants
GITHUB_API_BASE = "https://api.github.com"
REPO_PATH = "pingcap/tidb"
USER_AGENT = "github-pr-analyzer/1.0"

# GitHub API token should be set as an environment variable
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def make_github_request(url: str, params: Dict[str, Any] = None) -> Dict[str, Any] | None:
    """Make a request to the GitHub API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Add authorization if token is available
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"API request failed: {str(e)}"}

@mcp.tool()
async def get_pr_status(pr_number: int) -> str:
    """Get the status of a PR (open, closed, or merged).
    
    Args:
        pr_number: The PR number to check
    """
    url = f"{GITHUB_API_BASE}/repos/{REPO_PATH}/pulls/{pr_number}"
    pr_data = await make_github_request(url)
    
    if "error" in pr_data:
        return f"Error fetching PR status: {pr_data['error']}"
    
    if not pr_data:
        return f"PR #{pr_number} not found"
    
    # Get the basic status
    status = pr_data.get("state", "unknown")
    
    # Check if PR is merged
    merged = pr_data.get("merged", False)
    if merged:
        status = "merged"
    
    # Add more details
    created_at = pr_data.get("created_at", "unknown date")
    updated_at = pr_data.get("updated_at", "unknown date")
    
    return f"""
PR #{pr_number} Status: {status.upper()}
Title: {pr_data.get('title', 'No title')}
Created: {created_at}
Last Updated: {updated_at}
URL: {pr_data.get('html_url', '')}
"""

@mcp.tool()
async def get_pr_labels(pr_number: int) -> str:
    """Get all labels applied to a PR.
    
    Args:
        pr_number: The PR number to check
    """
    url = f"{GITHUB_API_BASE}/repos/{REPO_PATH}/pulls/{pr_number}"
    pr_data = await make_github_request(url)
    
    if "error" in pr_data:
        return f"Error fetching PR labels: {pr_data['error']}"
    
    if not pr_data:
        return f"PR #{pr_number} not found"
    
    # Extract labels
    labels = pr_data.get("labels", [])
    
    if not labels:
        return f"PR #{pr_number} has no labels"
    
    label_list = "\n".join([f"- {label.get('name', 'Unknown')} ({label.get('description', 'No description')})" 
                           for label in labels])
    
    return f"""
PR #{pr_number} Labels:
{label_list}
"""

@mcp.tool()
async def get_pr_details(pr_number: int) -> str:
    """Get detailed information about a PR including author, commits, files changed, and analysis.
    
    Args:
        pr_number: The PR number to check
    """
    # Get basic PR data
    pr_url = f"{GITHUB_API_BASE}/repos/{REPO_PATH}/pulls/{pr_number}"
    pr_data = await make_github_request(pr_url)
    
    if "error" in pr_data:
        return f"Error fetching PR details: {pr_data['error']}"
    
    if not pr_data:
        return f"PR #{pr_number} not found"
    
    # Get PR files
    files_url = f"{GITHUB_API_BASE}/repos/{REPO_PATH}/pulls/{pr_number}/files"
    files_data = await make_github_request(files_url)
    
    if "error" in files_data:
        files_info = "Error fetching files data"
    else:
        files_list = [f"- {file.get('filename', 'Unknown')} ({file.get('status', 'Unknown')})" for file in files_data]
        files_info = "\n".join(files_list[:20])  # Limit to 20 files to avoid too long responses
        if len(files_data) > 20:
            files_info += f"\n... and {len(files_data) - 20} more files"
    
    # Get PR commits
    commits_url = f"{GITHUB_API_BASE}/repos/{REPO_PATH}/pulls/{pr_number}/commits"
    commits_data = await make_github_request(commits_url)
    
    if "error" in commits_data:
        commits_count = "Error fetching commits data"
    else:
        commits_count = len(commits_data)
    
    # Extract PR details
    author = pr_data.get("user", {}).get("login", "Unknown")
    title = pr_data.get("title", "No title")
    body = pr_data.get("body", "No description")
    
    # Prepare summary of the PR's purpose
    summary = f"""
Based on the PR title, description, and changed files, this PR appears to be:
- Title: {title}
- Description summary: {body[:200]}{'...' if len(body) > 200 else ''}
- Changed {len(files_data) if isinstance(files_data, list) else 'unknown number of'} files
- Contains {commits_count} commits
    """
    
    return f"""
PR #{pr_number} Details:
Author: {author}
Title: {title}
Commits: {commits_count}

Changed Files:
{files_info}

PR Analysis:
{summary}
"""

@mcp.tool()
async def get_pr_reviewers(pr_number: int) -> str:
    """Get information about required reviewers for a PR and the files that trigger these requirements.
    
    Args:
        pr_number: The PR number to check
    """
    # First try to read PR's issue_comments, which usually contains ti-chi-bot's comments
    issue_comments_url = f"{GITHUB_API_BASE}/repos/{REPO_PATH}/issues/{pr_number}/comments"
    params = {
        "sort": "updated",
        "direction": "desc",
        "per_page": 30
    }
    
    page = 1
    approval_comment = None
    max_pages = 5
    
    # Find approval comments
    while approval_comment is None and page <= max_pages:
        try:
            params["page"] = page
            comments_data = await make_github_request(issue_comments_url, params=params)
            
            if isinstance(comments_data, dict) and "error" in comments_data:
                return f"Error fetching PR comments: {comments_data['error']}"
            
            if not comments_data or not isinstance(comments_data, list):
                break
            
            # Find ti-chi-bot's APPROVALNOTIFIER comments
            for comment in comments_data:
                login = comment.get('user', {}).get('login', '')
                if login in ['ti-chi-bot', 'ti-chi-bot[bot]']:
                    body = comment.get('body', '')
                    if body and '[APPROVALNOTIFIER]' in body:
                        approval_comment = comment
                        break
            
            if approval_comment or len(comments_data) < params["per_page"]:
                break
                
            page += 1
        except Exception as e:
            return f"Error processing PR comments: {str(e)}"
    
    if not approval_comment:
        return f"No approval notification found from ti-chi-bot on PR #{pr_number}. The PR might be very new or ti-chi-bot hasn't analyzed it yet."
    
    # Parse comment content
    try:
        body = approval_comment.get('body', '')
        logger.info(f"Found approval comment for PR #{pr_number}")
        
        # Check if PR has been approved
        approval_status = "NOT APPROVED"
        if "This PR is **NOT APPROVED**" in body:
            approval_status = "NOT APPROVED"
        elif "This PR is **APPROVED**" in body:
            approval_status = "APPROVED"
        
        logger.info(f"PR #{pr_number} approval status: {approval_status}")
        
        # Extract recommended approvers - multiple pattern matching
        recommended_approvers = []
        
        # Method 1: Extract please assign [name](url) format from text
        assign_pattern = r"please assign ((?:\[[^\]]+\]\([^)]+\)(?:,\s*)?)+)"
        assign_match = re.search(assign_pattern, body, re.IGNORECASE)
        
        if assign_match:
            # Extract all approver names and links
            approver_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
            approvers_text = assign_match.group(1)
            approvers = re.findall(approver_pattern, approvers_text)
            recommended_approvers = [{"name": name, "url": url} for name, url in approvers]
        
        # Method 2: Try to extract from META JSON
        meta_pattern = r"<!-- META=(.*?) -->"
        meta_match = re.search(meta_pattern, body)
        if meta_match and not recommended_approvers:
            try:
                import json
                meta_json = json.loads(meta_match.group(1).replace("\\\"", "\""))
                if "approvers" in meta_json:
                    for approver in meta_json["approvers"]:
                        recommended_approvers.append({
                            "name": approver,
                            "url": f"https://github.com/{approver}"
                        })
            except Exception as e:
                logger.error(f"Error parsing META JSON: {e}")
        
        # Extract required approval files paths
        required_owners_files = []
        details_pattern = r"<details[^>]*>(.*?)</details>"
        details_match = re.search(details_pattern, body, re.DOTALL)
        
        if details_match:
            details_content = details_match.group(1)
            # Identify "Needs approval from an approver in each of these files:" paragraph
            if "Needs approval from an approver in each of these files:" in details_content:
                # Find OWNERS file paths and links
                owners_pattern = r"\*\*\[([^\]]+)\]\(([^)]+)\)\*\*"
                owners_files = re.findall(owners_pattern, details_content)
                required_owners_files = [{"path": path, "url": url} for path, url in owners_files]
        
        # Use a more structured format
        result = f"Based on the query results, PR #{pr_number} "
        
        if approval_status == "APPROVED":
            result += "has been **APPROVED** and is ready to be merged.\n"
        else:
            result += "requires review and approval from the following:\n\n"
            
            if recommended_approvers:
                result += "* **Recommended Approvers (Need approval from each of them):**\n"
                for approver in recommended_approvers:
                    result += f"    * {approver['name']} ({approver['url']})\n"
            
            if required_owners_files:
                result += "* **Required Approvals from Owners of:**\n"
                for file in required_owners_files:
                    result += f"    * {file['path']} ({file['url']})\n"
            
            if approval_status == "NOT APPROVED":
                result += "\nThis PR needs approvals before it can be merged. "
                if recommended_approvers:
                    approver_names = [a["name"] for a in recommended_approvers]
                    result += f"Please request reviews from ALL of these approvers: {', '.join(approver_names)}. You need approval from EACH of them to merge this PR."
                elif required_owners_files:
                    result += "Please request reviews from the owners of the files listed above."
                else:
                    result += "Please request reviews from the appropriate owners."
        
        result += "\n\nSUGGESTED_RESPONSE_FORMAT: Please present this information in a bullet-point format with clear sections for approvers(provide the github url) and required files(provide the github url)."
        
        return result
    except Exception as e:
        return f"Error parsing approval comment: {str(e)}\n\nOriginal comment: {body[:200]}..."

if __name__ == "__main__":
    # Set command line argument parsing
    parser = argparse.ArgumentParser(description="GitHub PR Analyzer")
    parser.add_argument("--sse", action="store_true", help="Use SSE transport mode instead of default stdio")
    args = parser.parse_args()
    
    # Choose transport mode based on command line argument
    transport_mode = "sse" if args.sse else "stdio"
    
    # Initialize and run server
    mcp.run(transport=transport_mode)
