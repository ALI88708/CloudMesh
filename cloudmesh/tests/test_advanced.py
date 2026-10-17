"""Unit tests for benchmark and notification contracts."""

import json
import urllib.error
import urllib.request
from unittest.mock import Mock

import pytest

from core import advanced


def test_cpu_benchmark_counts_work_until_the_duration_boundary(monkeypatch):
    monkeypatch.setattr(advanced.time, "time", Mock(side_effect=[10, 10, 10.5, 11, 11.5]))

    assert advanced.benchmark_cpu(duration=1.5) == {"score": 2, "duration": 1.5}


@pytest.mark.parametrize("duration", [0, -1])
def test_cpu_benchmark_nonpositive_duration_does_no_work(monkeypatch, duration):
    monkeypatch.setattr(advanced.time, "time", Mock(return_value=10))
    hashing = Mock()
    monkeypatch.setattr(advanced.hashlib, "md5", hashing)

    if duration == 0:
        with pytest.raises(ZeroDivisionError):
            advanced.benchmark_cpu(duration)
    else:
        assert advanced.benchmark_cpu(duration) == {"score": 0, "duration": duration}
    hashing.assert_not_called()


@pytest.fixture(params=["telegram", "discord"])
def notification(request, tmp_path, monkeypatch):
    manager = advanced.NotifyManager(tmp_path / "notify.json")
    manager.setup_telegram("synthetic-token", "synthetic-chat")
    manager.setup_discord("https://discord.example.test/webhook")
    delivery = Mock()
    monkeypatch.setattr(urllib.request, "urlopen", delivery)
    return request.param, getattr(manager, f"send_{request.param}"), delivery


@pytest.mark.parametrize("message", ["", "hello", "line one\n雪 🐇"])
def test_notification_sends_json_with_a_bounded_timeout(notification, message):
    provider, send, delivery = notification

    assert send(message) is True

    delivery.assert_called_once()
    (request,), kwargs = delivery.call_args
    assert kwargs == {"timeout": 10}
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    if provider == "telegram":
        assert request.full_url == "https://api.telegram.org/botsynthetic-token/sendMessage"
        assert json.loads(request.data) == {"chat_id": "synthetic-chat", "text": message}
    else:
        assert request.full_url == "https://discord.example.test/webhook"
        assert json.loads(request.data) == {"content": message}


@pytest.mark.parametrize(
    ("provider", "config"),
    [
        ("telegram", {}),
        ("telegram", {"bot_token": "synthetic-token"}),
        ("telegram", {"chat_id": "synthetic-chat"}),
        ("discord", {}),
        ("discord", {"webhook_url": ""}),
    ],
)
def test_notification_without_credentials_does_not_contact_provider(
    tmp_path, monkeypatch, provider, config
):
    manager = advanced.NotifyManager(tmp_path / "notify.json")
    manager._config = {provider: config}
    delivery = Mock()
    monkeypatch.setattr(urllib.request, "urlopen", delivery)

    assert getattr(manager, f"send_{provider}")("hello") is False
    delivery.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [TimeoutError("delivery timed out"), urllib.error.URLError("offline")],
    ids=["timeout", "connection-error"],
)
def test_notification_reports_delivery_errors_as_false(notification, error):
    _, send, delivery = notification
    delivery.side_effect = error

    assert send("hello") is False
    delivery.assert_called_once()


def test_notification_reports_serialization_errors_without_delivery(notification):
    _, send, delivery = notification

    assert send(object()) is False
    delivery.assert_not_called()


def test_notification_reports_request_construction_errors(notification, monkeypatch):
    _, send, delivery = notification
    monkeypatch.setattr(urllib.request, "Request", Mock(side_effect=ValueError("bad URL")))

    assert send("hello") is False
    delivery.assert_not_called()
