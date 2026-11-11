import threading
import time

import pytest
from urllib.error import HTTPError, URLError
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
    assert "height:calc(100vh - 365px)" in progress_page
    assert "IBM Plex Sans" in progress_page
    assert "function renderLogs" in progress_page
    assert "log-error" in progress_page


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



@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize("chosen", [False, True])
@pytest.mark.parametrize("tools", [[], TOOLS])
def test_web_build_setting_is_submitted_before_build_starts(monkeypatch, initial, chosen, tools):
    saved = []
    errors = []
    workers = []

    def save(selection, report, cancel_event, *, allow_tool_failures):
        saved.append((selection, allow_tool_failures))
        report(1, 1, "Complete")

    def browser(url):
        def interact():
            parsed = urlsplit(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            finished = False
            try:
                with urlopen(url, timeout=3) as response:
                    page = response.read().decode()
                assert 'name="allow_tool_failures"' in page
                assert ('name="allow_tool_failures" value="1" checked' in page) is initial
                assert not saved
                save_url = f"{base}/save?{parsed.query}"
                for value in ('true', ['1', '1']):
                    request = Request(save_url, data=urlencode({'allow_tool_failures': value}, doseq=True).encode())
                    with pytest.raises(HTTPError) as error:
                        urlopen(request, timeout=3)
                    assert error.value.code == 400
                    assert not saved
                form = {'enabled': ['httpx']}
                if chosen:
                    form['allow_tool_failures'] = ['1']
                with urlopen(Request(save_url, data=urlencode(form, doseq=True).encode()), timeout=3) as response:
                    assert response.status == 202
                    assert b'My build progress' in response.read()
                with urlopen(url, timeout=3) as response:
                    assert b'My build progress' in response.read()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    with urlopen(f"{base}/status?{parsed.query}", timeout=3) as response:
                        status = json.load(response)
                    if status['done']:
                        assert status['success']
                        finished = True
                        break
                assert finished
            except BaseException as error:
                errors.append(error)
            finally:
                if not finished:
                    try:
                        urlopen(f"{base}/cancel?{parsed.query}", timeout=3).close()
                    except (URLError, OSError):
                        pass
        thread = threading.Thread(target=interact, daemon=True)
        workers.append(thread)
        thread.start()
        return True

    monkeypatch.setattr('nihil.features.tool_selector_web.webbrowser.open', browser)
    result = select_tools_web(tools, set(), 'test', on_save=save, action_label='Start build',
                              allow_tool_failures=initial, page_title='My build progress')
    for worker in workers:
        worker.join(timeout=3)
    assert not errors
    assert saved == [({'nuclei'} if tools else set(), chosen)]
    assert result == saved[0][0]
