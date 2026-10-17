"""Unit tests for GitHub Checks + PR comment helpers (mocked HTTP)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from devdeploy_api import github_checks


def _settings(*, mock: bool = False) -> SimpleNamespace:
    return SimpleNamespace(effective_github_mock=mock)


def test_create_check_run_skips_in_mock_mode():
    assert (
        github_checks.create_check_run(
            _settings(mock=True),
            installation_id=1,
            repo_full_name="org/repo",
            head_sha="abc",
        )
        is None
    )


def test_create_check_run_posts_and_returns_id():
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": 4242}
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with (
        patch(
            "devdeploy_api.github_checks.create_installation_token",
            return_value={"token": "tok"},
        ),
        patch("devdeploy_api.github_checks.httpx.Client", return_value=mock_client),
    ):
        cid = github_checks.create_check_run(
            _settings(mock=False),
            installation_id=99,
            repo_full_name="org/repo",
            head_sha="deadbeef",
            details_url="http://localhost/deployments/1",
        )
    assert cid == 4242
    mock_client.post.assert_called_once()
    body = mock_client.post.call_args.kwargs["json"]
    assert body["status"] == "in_progress"
    assert body["head_sha"] == "deadbeef"


def test_complete_check_run_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.patch.return_value = mock_resp

    with (
        patch(
            "devdeploy_api.github_checks.create_installation_token",
            return_value={"token": "tok"},
        ),
        patch("devdeploy_api.github_checks.httpx.Client", return_value=mock_client),
    ):
        ok = github_checks.complete_check_run(
            _settings(mock=False),
            installation_id=1,
            repo_full_name="org/repo",
            check_run_id=4242,
            conclusion="failure",
            title="Preview failed",
            summary="Build failed",
        )
    assert ok is True
    body = mock_client.patch.call_args.kwargs["json"]
    assert body["conclusion"] == "failure"
    assert body["status"] == "completed"


def test_comment_on_pull_request():
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with (
        patch(
            "devdeploy_api.github_checks.create_installation_token",
            return_value={"token": "tok"},
        ),
        patch("devdeploy_api.github_checks.httpx.Client", return_value=mock_client),
    ):
        ok = github_checks.comment_on_pull_request(
            _settings(mock=False),
            installation_id=1,
            repo_full_name="org/repo",
            pr_number=7,
            body="preview ready",
        )
    assert ok is True
    assert mock_client.post.call_args.args[0].endswith("/issues/7/comments")
