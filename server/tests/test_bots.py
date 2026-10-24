import pytest
from squint.bots.reply import format_reply
from squint.bots import whatsapp
from squint.schemas import Verdict, Haptic


def verdict(tier="likely_synthetic", say="Likely AI.", evidence=None, factchecks=None):
    return Verdict(
        check_id="c1", kind="image", tier=tier, p=0.9, confidence="high",
        haptic=Haptic(pattern=[0, 650], amplitudes=[0, 255], label="one long buzz"),
        say=say, headline="Likely AI-made", evidence=evidence or ["hive puts it at 90% synthetic"],
        signals=[], factchecks=factchecks or [], ms=10,
    )


def test_reply_has_emoji_headline_and_evidence():
    txt = format_reply(verdict(factchecks=[{"publisher": "Reuters", "rating": "False", "url": "https://r.example/x"}]), hint=True)
    assert txt.startswith("🔴 Likely AI-made")
    assert "• hive puts it at 90% synthetic" in txt
    assert "https://r.example/x" in txt
    assert "wrong" in txt


def test_reply_for_unclear_is_grey():
    assert format_reply(verdict("unclear", "Can't tell from this.")).startswith("⚪")


class FakeState:
    pass


class FakeApp:
    def __init__(self, pipeline, index):
        self.state = FakeState()
        self.state.pipeline = pipeline
        self.state.index = index
        from squint.config import Settings
        self.state.settings = Settings(db_url="sqlite:///:memory:")


async def test_whatsapp_text_message_round_trip(pipeline, index, monkeypatch):
    sent = []

    async def fake_send(app, to, text):
        sent.append((to, text))

    monkeypatch.setattr(whatsapp, "_send", fake_send)
    app = FakeApp(pipeline, index)
    body = {"entry": [{"changes": [{"value": {"messages": [{"from": "15551234567", "type": "text", "text": {"body": "x " * 60}}]}}]}]}
    await whatsapp.handle(app, body)
    assert sent and sent[0][0] == "15551234567"
    assert "wrong" in sent[0][1]
    await whatsapp.handle(app, {"entry": [{"changes": [{"value": {"messages": [{"from": "15551234567", "type": "text", "text": {"body": "wrong"}}]}}]}]})
    assert "noted" in sent[-1][1]
    assert index.stats()["feedback"] == {"unsure": 1}


async def test_whatsapp_short_text_gets_help(pipeline, index, monkeypatch):
    sent = []

    async def fake_send(app, to, text):
        sent.append(text)

    monkeypatch.setattr(whatsapp, "_send", fake_send)
    await whatsapp.handle(FakeApp(pipeline, index), {"entry": [{"changes": [{"value": {"messages": [{"from": "1", "type": "text", "text": {"body": "hi"}}]}}]}]})
    assert "forward me" in sent[0]
