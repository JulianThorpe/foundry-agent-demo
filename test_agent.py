import requests
from agent import (
    ALLOWED_PAGES,
    MAX_ITERATIONS,
    execute_tool_call,
    get_current_temperature,
    navigate_to_page,
)


# --- navigate_to_page: the permission boundary ---


def test_allowed_page_succeeds():
    result = navigate_to_page("pricing")
    assert result["ok"] is True
    assert result["page"] == "pricing"


def test_unknown_page_is_rejected():
    result = navigate_to_page("admin")
    assert result["ok"] is False
    assert "unknown page" in result["error"]


def test_every_allowed_page_is_reachable():
    for page in ALLOWED_PAGES:
        assert navigate_to_page(page)["ok"] is True


def test_iteration_cap_is_bounded():
    assert 0 < MAX_ITERATIONS <= 10


# --- get_current_temperature: an external call that can fail ---


class FakeResponse:
    def __init__(self, status_code=200, payload=None, raises=False):
        self.status_code = status_code
        self._payload = payload
        self._raises = raises

    def json(self):
        if self._raises:
            raise ValueError("not json")
        return self._payload


def test_coordinates_are_validated_before_the_call(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("should not have called the service")

    monkeypatch.setattr(requests, "get", fail)
    result = get_current_temperature(200, 0)
    assert result["ok"] is False
    assert "out of range" in result["error"]


def test_network_failure_returns_structured_error(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(requests, "get", raise_timeout)
    result = get_current_temperature(-35.28, 149.13)
    assert result["ok"] is False
    assert "unreachable" in result["error"]


def test_server_error_returns_structured_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(status_code=503))
    result = get_current_temperature(-35.28, 149.13)
    assert result["ok"] is False
    assert "503" in result["error"]


def test_malformed_response_returns_structured_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(raises=True))
    result = get_current_temperature(-35.28, 149.13)
    assert result["ok"] is False
    assert "unexpected response shape" in result["error"]


def test_successful_lookup_returns_temperature(monkeypatch):
    payload = {"current": {"temperature_2m": 14.2}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(payload=payload))
    result = get_current_temperature(-35.28, 149.13)
    assert result["ok"] is True
    assert result["celsius"] == 14.2


# --- execute_tool_call: what happens when the model gets it wrong ---


def test_unknown_tool_is_rejected():
    result = execute_tool_call("delete_everything", "{}")
    assert result["ok"] is False
    assert "unknown tool" in result["error"]


def test_invalid_json_arguments_are_rejected():
    result = execute_tool_call("navigate_to_page", "{not json")
    assert result["ok"] is False
    assert "not valid JSON" in result["error"]


def test_wrong_argument_names_are_rejected():
    result = execute_tool_call("navigate_to_page", '{"url": "pricing"}')
    assert result["ok"] is False
    assert "wrong arguments" in result["error"]


def test_valid_call_is_routed_to_the_right_tool():
    result = execute_tool_call("navigate_to_page", '{"page": "contact"}')
    assert result == {"ok": True, "page": "contact"}
