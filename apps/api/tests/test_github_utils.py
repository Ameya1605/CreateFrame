import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import github_utils


@pytest.mark.anyio
async def test_create_atomic_commit_successful_flow():
    token = "ghp_mock_token"
    repo_url = "https://github.com/myorg/myrepo"
    files = {
        "spec.json": '{"version": "2.0"}',
        "packages/database/schema.prisma": "model User { id Int @id }",
    }

    mock_instance = AsyncMock()

    # 1. GET repo default branch
    resp_repo = MagicMock(status_code=200)
    resp_repo.json.return_value = {"default_branch": "main"}

    # 2. GET ref
    resp_ref = MagicMock(status_code=200)
    resp_ref.json.return_value = {"object": {"sha": "commit_sha_123"}}

    # 3. GET commit
    resp_commit = MagicMock(status_code=200)
    resp_commit.json.return_value = {"tree": {"sha": "tree_sha_base"}}

    # 4. POST tree
    resp_new_tree = MagicMock(status_code=201)
    resp_new_tree.json.return_value = {"sha": "tree_sha_new"}

    # 5. POST commit
    resp_new_commit = MagicMock(status_code=201)
    resp_new_commit.json.return_value = {"sha": "commit_sha_new"}

    # 6. PATCH ref
    resp_patch_ref = MagicMock(status_code=200)
    resp_patch_ref.json.return_value = {"object": {"sha": "commit_sha_new"}}

    mock_instance.get.side_effect = [resp_repo, resp_ref, resp_commit]
    mock_instance.post.side_effect = [resp_new_tree, resp_new_commit]
    mock_instance.patch.side_effect = [resp_patch_ref]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_instance

        result = await github_utils.create_atomic_commit(
            token=token,
            repo_url=repo_url,
            files=files,
            message="feat: atomic sync",
        )

        assert result["status"] == "success"
        assert result["commit_sha"] == "commit_sha_new"
        assert result["branch"] == "main"
        assert result["files_committed"] == 2


@pytest.mark.anyio
async def test_create_atomic_commit_branch_fallback():
    token = "ghp_mock_token"
    repo_url = "https://github.com/myorg/myrepo"
    files = {"spec.json": "{}"}

    mock_instance = AsyncMock()

    # GET repo fails or returns main
    resp_repo = MagicMock(status_code=200)
    resp_repo.json.return_value = {"default_branch": "main"}

    # GET main ref returns 404
    resp_ref_main = MagicMock(status_code=404, text="Branch not found")

    # GET master ref returns 200
    resp_ref_master = MagicMock(status_code=200)
    resp_ref_master.json.return_value = {"object": {"sha": "master_sha_123"}}

    resp_commit = MagicMock(status_code=200)
    resp_commit.json.return_value = {"tree": {"sha": "tree_master"}}

    resp_new_tree = MagicMock(status_code=201)
    resp_new_tree.json.return_value = {"sha": "tree_new"}

    resp_new_commit = MagicMock(status_code=201)
    resp_new_commit.json.return_value = {"sha": "commit_new"}

    resp_patch = MagicMock(status_code=200)

    mock_instance.get.side_effect = [resp_repo, resp_ref_main, resp_ref_master, resp_commit]
    mock_instance.post.side_effect = [resp_new_tree, resp_new_commit]
    mock_instance.patch.side_effect = [resp_patch]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_instance

        result = await github_utils.create_atomic_commit(
            token=token,
            repo_url=repo_url,
            files=files,
        )

        assert result["status"] == "success"
        assert result["branch"] == "master"
