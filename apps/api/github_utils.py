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
            "message": "Update spec.json from SpecOS",
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha
            
        put_res = await client.put(url, headers=headers, json=payload)
        return put_res.json()
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

async def push_file_to_github(token: str, repo_url: str, file_path: str, content: str, message: str = "Update from SpecOS"):
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
