import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

async def get_github_access_token(code: str):
    url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, data=data)
        return response.json()

async def get_github_user(token: str):
    url = "https://api.github.com/user"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json()

async def push_spec_to_github(token: str, repo_url: str, spec_content: str):
    # repo_url format: https://github.com/owner/repo
    repo_parts = repo_url.rstrip("/").split("/")
    owner = repo_parts[-2]
    repo = repo_parts[-1]
    
    file_path = "spec.json"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Check if file exists to get SHA
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        sha = None
        if res.status_code == 200:
            sha = res.json().get("sha")
        
        content_b64 = base64.b64encode(spec_content.encode()).decode()
        
        payload = {
            "message": "Update spec.json from CreateFrame",
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha
            
        put_res = await client.put(url, headers=headers, json=payload)
        return put_res.json()

async def fetch_spec_from_github(token: str, repo_url: str):
    repo_parts = repo_url.rstrip("/").split("/")
    owner = repo_parts[-2]
    repo = repo_parts[-1]
    
    file_path = "spec.json"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        if res.status_code != 200:
            return None
        data = res.json()
        content = data.get("content", "")
        try:
            decoded = base64.b64decode(content).decode("utf-8")
            import json
            return json.loads(decoded)
        except Exception:
            return None

async def get_github_repos(token: str):
    url = "https://api.github.com/user/repos?sort=updated&per_page=100"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json()

async def create_github_repo(token: str, name: str, private: bool = False):
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "name": name,
        "private": private,
        "auto_init": True # Creates README automatically
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        return response.json()

async def get_github_commits(token: str, owner: str, repo: str):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=15"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200: return []
        return [c["commit"]["message"] for c in response.json()]

async def push_file_to_github(token: str, repo_url: str, file_path: str, content: str, message: str = "Update from CreateFrame"):
    repo_parts = repo_url.rstrip("/").split("/")
    owner = repo_parts[-2]
    repo = repo_parts[-1]
    
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        sha = None
        if res.status_code == 200:
            sha = res.json().get("sha")
        
        content_b64 = base64.b64encode(content.encode()).decode()
        payload = {"message": message, "content": content_b64}
        if sha: payload["sha"] = sha
            
        put_res = await client.put(url, headers=headers, json=payload)
        return put_res.json()


async def create_atomic_commit(
    token: str,
    repo_url: str,
    files: dict,
    message: str = "Update from CreateFrame",
    branch: str = None,
) -> dict:
    """
    Creates a single atomic commit containing all modified files via the GitHub Git Data API.
    Avoids multi-commit churn and eliminates race conditions.
    """
    repo_parts = repo_url.rstrip("/").split("/")
    owner = repo_parts[-2]
    repo = repo_parts[-1]
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        # Determine target branch
        target_branch = branch
        if not target_branch:
            repo_res = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
            if repo_res.status_code == 200:
                target_branch = repo_res.json().get("default_branch", "main")
            else:
                target_branch = "main"

        # 1. Get branch commit SHA
        ref_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{target_branch}"
        ref_res = await client.get(ref_url, headers=headers)
        if ref_res.status_code != 200:
            for alt in ("master", "main"):
                if alt != target_branch:
                    alt_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{alt}"
                    alt_res = await client.get(alt_url, headers=headers)
                    if alt_res.status_code == 200:
                        target_branch = alt
                        ref_res = alt_res
                        ref_url = alt_url
                        break

        if ref_res.status_code != 200:
            raise RuntimeError(f"Could not resolve branch ref: {ref_res.text}")

        current_commit_sha = ref_res.json()["object"]["sha"]

        # 2. Get base tree SHA from commit
        commit_res = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/commits/{current_commit_sha}",
            headers=headers
        )
        if commit_res.status_code != 200:
            raise RuntimeError(f"Could not get commit info: {commit_res.text}")
        base_tree_sha = commit_res.json()["tree"]["sha"]

        # 3. Create tree containing all file updates
        tree_items = []
        for path, content in files.items():
            tree_items.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "content": content
            })

        tree_res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees",
            headers=headers,
            json={"base_tree": base_tree_sha, "tree": tree_items}
        )
        if tree_res.status_code not in (200, 201):
            raise RuntimeError(f"Could not create tree: {tree_res.text}")
        new_tree_sha = tree_res.json()["sha"]

        # 4. Create new commit
        new_commit_res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/commits",
            headers=headers,
            json={
                "message": message,
                "tree": new_tree_sha,
                "parents": [current_commit_sha]
            }
        )
        if new_commit_res.status_code not in (200, 201):
            raise RuntimeError(f"Could not create commit: {new_commit_res.text}")
        new_commit_sha = new_commit_res.json()["sha"]

        # 5. Update branch ref
        patch_res = await client.patch(
            ref_url,
            headers=headers,
            json={"sha": new_commit_sha, "force": False}
        )
        if patch_res.status_code != 200:
            raise RuntimeError(f"Could not update branch ref: {patch_res.text}")

        return {
            "status": "success",
            "commit_sha": new_commit_sha,
            "branch": target_branch,
            "files_committed": len(files)
        }


async def create_branch(token: str, repo_url: str, branch_name: str, from_branch: str = "main") -> dict:
    """Creates a new git branch pointing to the tip of from_branch."""
    repo_parts = repo_url.rstrip("/").split("/")
    owner = repo_parts[-2]
    repo = repo_parts[-1]
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Get SHA of from_branch
        ref_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{from_branch}"
        ref_res = await client.get(ref_url, headers=headers)
        if ref_res.status_code != 200:
            for alt in ("master", "main"):
                alt_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{alt}"
                alt_res = await client.get(alt_url, headers=headers)
                if alt_res.status_code == 200:
                    ref_res = alt_res
                    break

        if ref_res.status_code != 200:
            raise RuntimeError(f"Could not find base branch {from_branch}")

        base_sha = ref_res.json()["object"]["sha"]

        # 2. Create new branch ref
        create_res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha}
        )
        if create_res.status_code not in (200, 201):
            raise RuntimeError(f"Could not create branch {branch_name}: {create_res.text}")

        return {"branch": branch_name, "sha": base_sha}


async def create_pull_request(
    token: str,
    repo_url: str,
    head: str,
    base: str,
    title: str,
    body: str,
) -> dict:
    """Opens a GitHub Pull Request from head branch to base branch."""
    repo_parts = repo_url.rstrip("/").split("/")
    owner = repo_parts[-2]
    repo = repo_parts[-1]
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers,
            json={"head": head, "base": base, "title": title, "body": body}
        )
        if res.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create pull request: {res.text}")
        data = res.json()
        return {
            "pr_number": data.get("number"),
            "pr_url": data.get("html_url"),
            "head": head,
            "base": base,
            "title": title
        }


