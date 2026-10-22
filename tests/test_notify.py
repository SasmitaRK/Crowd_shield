import io
import json
import urllib.error

from crowdshield import notify


class FakeReply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def configure(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRET")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")


def test_not_set_up_means_nothing_is_sent(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sent")))
    ok, message = notify.send_telegram("hi")
    assert not ok and "not set up" in message


def test_a_message_goes_to_the_right_chat(monkeypatch):
    configure(monkeypatch)
    seen = {}

    def fake(request, timeout):
        seen["url"], seen["data"], seen["timeout"] = request.full_url, request.data.decode(), timeout
        return FakeReply(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake)
    ok, message = notify.send_telegram("zone A is crowded")
    assert ok and seen["url"].endswith("/sendMessage") and "chat_id=42" in seen["data"]
    assert seen["timeout"] == notify.TIMEOUT_S


def test_a_photo_is_sent_as_a_photo(monkeypatch):
    configure(monkeypatch)
    seen = {}
    monkeypatch.setattr(notify.urllib.request, "urlopen",
                        lambda request, timeout: (seen.update(url=request.full_url, body=request.data),
                                                  FakeReply(b'{"ok": true}'))[1])
    ok, _ = notify.send_telegram("look", b"\xff\xd8jpegbytes")
    assert ok and seen["url"].endswith("/sendPhoto") and b"jpegbytes" in seen["body"]


def test_errors_are_explained_and_never_leak_the_token(monkeypatch):
    configure(monkeypatch)
    for code, hint in ((401, "token is wrong"), (400, "chat id is wrong"), (403, "blocked")):
        def boom(request, timeout, code=code):
            raise urllib.error.HTTPError(request.full_url, code, "x", {}, None)

        monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
        ok, message = notify.send_telegram("hi")
        assert not ok and hint in message and "SECRET" not in message
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(TimeoutError("SECRET")))
    ok, message = notify.send_telegram("hi")
    assert not ok and "SECRET" not in message


def test_alert_text_is_short_and_says_what_to_do():
    text = notify.alert_text("A", "Sangam Nose", "Critical", 88820, 4.8, 3.2)
    assert "CRITICAL" in text and "88,820" in text and "4.8 per m2" in text and "3 min" in text
    assert len(text) < 300


def test_broadcast_reports_when_no_channel_exists(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("GMAIL_USER", raising=False)
    assert "No alert channel" in notify.broadcast("x")[0]
