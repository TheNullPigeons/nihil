import threading
import json
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from nihil.features.tool_selector_web import (
    _disabled_from_enabled,
    _render_page,
    _render_progress_page,
    _render_result,
    select_tools_web,
)


TOOLS = [
    {"name": "vim", "cmd": "vim", "category": "core_tools", "mandatory": True},
    {"name": "httpx", "cmd": "httpx", "category": "mod_web", "mandatory": False},
    {"name": "nuclei", "cmd": "nuclei", "category": "mod_web", "mandatory": False},
]


def test_web_selector_validates_selection_and_escapes_html():
    assert _disabled_from_enabled(TOOLS, {"vim", "httpx", "unknown"}) == {"nuclei"}
    page = _render_page(
        TOOLS + [{"name": "<script>", "cmd": "x", "category": "bad", "mandatory": False}],
        {"nuclei"},
        "alice/nihil-images",
        "token",
    ).decode()
    assert "&lt;script&gt;" in page
    assert 'value="<script>"' not in page
    assert 'value="httpx" checked' in page
    assert 'value="nuclei"' in page and 'value="nuclei" checked' not in page
    assert 'id="category"' in page
    assert '<option value="mod_web">mod_web</option>' in page
    assert '<option value="selected">Selected</option>' in page
    assert 'data-category-toggle="mod_web"' in page

    result = _render_result("Selection saved", "You may close this tab.", True).decode()
    assert 'class="icon success"' in result
    assert "TheNullPigeons" in result

    progress_page = _render_progress_page("token", can_cancel=True).decode()
    assert "View live logs on GitHub" in progress_page
    assert "Cancel build" in progress_page
    assert "Complete build logs" in progress_page


def test_web_selector_serves_and_accepts_selection(monkeypatch):
    worker = None

    def open_browser(url):
        nonlocal worker

        def submit():
            with urlopen(url) as response:
                assert response.status == 200
            parsed = urlsplit(url)
            save_url = f"{parsed.scheme}://{parsed.netloc}/save?{parsed.query}"
            request = Request(save_url, data=urlencode({"enabled": "httpx"}).encode())
            with urlopen(request) as response:
                assert response.status == 200

        worker = threading.Thread(target=submit)
        worker.start()
        return True

    monkeypatch.setattr("nihil.features.tool_selector_web.webbrowser.open", open_browser)
    assert select_tools_web(TOOLS, set(), "test") == {"nuclei"}
    worker.join()


def test_web_selector_runs_workflow_and_reports_progress(monkeypatch):
    worker = None
    saved = []

    def save(selection, report, cancel_event):
        saved.append(selection)
        assert not cancel_event.is_set()
        report(2, 3, "Building image", "https://github.test/run/1", "all build logs")

    def open_browser(url):
        nonlocal worker

        def submit_and_poll():
            parsed = urlsplit(url)
            query = parsed.query
            save_url = f"{parsed.scheme}://{parsed.netloc}/save?{query}"
            request = Request(save_url, data=urlencode({"enabled": "httpx"}).encode())
            with urlopen(request) as response:
                assert response.status == 202
                assert b"Building your image" in response.read()
            status_url = f"{parsed.scheme}://{parsed.netloc}/status?{query}"
            with urlopen(status_url) as response:
                status = json.load(response)
            assert status["done"] is True
            assert status["success"] is True
            assert status["logs_ready"] is True
            logs_url = f"{parsed.scheme}://{parsed.netloc}/logs?{query}"
            with urlopen(logs_url) as response:
                assert response.read() == b"all build logs"

        worker = threading.Thread(target=submit_and_poll)
        worker.start()
        return True

    monkeypatch.setattr("nihil.features.tool_selector_web.webbrowser.open", open_browser)
    assert select_tools_web(TOOLS, set(), "test", on_save=save, action_label="Apply & build") == {"nuclei"}
    worker.join()
    assert saved == [{"nuclei"}]
