import base64
import os

from fastmcp import FastMCP
import httpx

from cli.utils.pat_utils import get_github_token

mcp = FastMCP("github")

def get_client() -> httpx.AsyncClient:
    pat = get_github_token()
    return httpx.AsyncClient(
        base_url="https://api.github.com",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {pat or ''}",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    )

@mcp.tool()
async def get_repo(owner: str, repo: str) -> dict:
    """Get information about a GitHub repository including default branch, stars, and description.

    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.

    Returns:
        dict: A dictionary containing the repository's full name, description, default branch, star count, and URL.
    """
    async with get_client() as client:
        response = await client.get(f"/repos/{owner}/{repo}")
        response.raise_for_status()
        data = response.json()

        return {
            "full_name": data["full_name"],
            "description": data["description"],
            "default_branch": data["default_branch"],
            "stars": data["stargazers_count"],
            "url": data["html_url"]
        }

@mcp.tool()
async def get_file(owner: str, repo: str, path: str) -> dict:
    """Get a file's contents from a GitHub repository.
    
    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.
        path (str): The path to the file.

    Returns:
        dict: A dictionary containing the file's path, content, and SHA.
    """
    async with get_client() as client:
        response = await client.get(f"/repos/{owner}/{repo}/contents/{path}")
        response.raise_for_status()
        data = response.json()

        return {
            "path": data["path"],
            "content": base64.b64decode(data["content"]).decode(),
            "sha": data["sha"]
        }

@mcp.tool()
async def create_branch(owner: str, repo: str, branch: str, base_branch: str = "main") -> dict:
    """Create a new branch in a GitHub repository.
    
    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.
        branch (str): The name of the new branch to create.
        base_branch (str): The name of the branch to branch from (default: "main").
    
    Returns:
        dict: A dictionary containing the new branch's reference and SHA.
    """
    async with get_client() as client:
        ref_response = await client.get(f"/repos/{owner}/{repo}/git/ref/heads/{base_branch}")
        ref_response.raise_for_status()
        sha = ref_response.json()["object"]["sha"]

        response = await client.post(f"/repos/{owner}/{repo}/git/refs", json={
            "ref": f"refs/heads/{branch}",
            "sha": sha
        })
        response.raise_for_status()
        data = response.json()

        return {
            "ref": data["ref"],
            "sha": data["object"]["sha"]
        }

@mcp.tool()
async def create_pull_request(owner: str, repo: str, title: str, head: str, base: str) -> dict:
    """Create a pull request in a GitHub repository.
    
    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.
        title (str): The title of the pull request.
        head (str): The branch to merge from.
        base (str): The branch to merge into.
    
    Returns:
        dict: A dictionary containing the pull request's number, title, URL, and state.
    """
    async with get_client() as client:
        response = await client.post(f"/repos/{owner}/{repo}/pulls", json={
            "title": title,
            "head": head,
            "base": base
        })
        response.raise_for_status()
        data = response.json()

        return {
            "number": data["number"],
            "title": data["title"],
            "url": data["html_url"],
            "state": data["state"]
        }

@mcp.tool()
async def list_pull_requests(owner: str, repo: str) -> list:
    """List all pull requests in a GitHub repository.
    
    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.

    Returns:
        list: A list of dictionaries, each containing a pull request's number, title, URL, and state.
    """
    async with get_client() as client:
        response = await client.get(f"/repos/{owner}/{repo}/pulls")
        response.raise_for_status()
        return [
            {
                "number": pr["number"],
                "title": pr["title"],
                "url": pr["html_url"],
                "state": pr["state"]
            }
            for pr in response.json()
        ]

@mcp.tool()
async def create_issue(owner: str, repo: str, title: str, body: str) -> dict:
    """Create an issue in a GitHub repository.
    
    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.
        title (str): The title of the issue.
        body (str): The body of the issue.

    Returns:
        dict: A dictionary containing the issue's number, title, URL, and state.
    """
    async with get_client() as client:
        response = await client.post(f"/repos/{owner}/{repo}/issues", json={
            "title": title,
            "body": body
        })
        response.raise_for_status()
        data = response.json()
        return {
            "number": data["number"],
            "title": data["title"],
            "url": data["html_url"]
        }

@mcp.tool()
async def list_issues(owner: str, repo: str) -> list:
    """List all issues in a GitHub repository.
    
    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.

    Returns:
        list: A list of dictionaries, each containing an issue's number, title, URL, and state.
    """
    async with get_client() as client:
        response = await client.get(f"/repos/{owner}/{repo}/issues")
        response.raise_for_status()
        return [
            {
                "number": issue["number"],
                "title": issue["title"],
                "url": issue["html_url"],
                "state": issue["state"]
            }
            for issue in response.json()
        ]

@mcp.tool()
async def create_fork(owner: str, repo: str) -> dict:
    """Create a fork of a GitHub repository.
    
    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.

    Returns:
        dict: A dictionary containing the fork's full name and URL.
    """
    async with get_client() as client:
        response = await client.post(f"/repos/{owner}/{repo}/forks")
        response.raise_for_status()
        data = response.json()
        return {
            "full_name": data["full_name"],
            "url": data["html_url"]
        }

if __name__ == "__main__":
    mcp.run(transport="stdio")
