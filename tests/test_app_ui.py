"""Tests for the FastAPI UI wrapper."""

from starlette.requests import Request

from openenv_bug_triage.app import index


def _request(root_path: str = "") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "root_path": root_path,
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )


def test_index_renders_ui_assets_at_root():
    response = index(_request())
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert 'href="/ui/styles.css"' in body
    assert 'src="/ui/app.js"' in body
    assert 'window.OPENENV_BASE_PATH = ""' in body


def test_index_renders_proxy_aware_asset_paths():
    response = index(_request("/spaces/demo/bug-triage"))
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert 'href="/spaces/demo/bug-triage/ui/styles.css"' in body
    assert 'src="/spaces/demo/bug-triage/ui/app.js"' in body
    assert 'window.OPENENV_BASE_PATH = "/spaces/demo/bug-triage"' in body
