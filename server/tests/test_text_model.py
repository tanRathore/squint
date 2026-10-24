import os
import pytest
from squint.providers.textmodel import TextModel, DEFAULT
from squint.pipeline import Pipeline

HERE = os.path.dirname(__file__)
pytestmark = pytest.mark.skipif(not os.path.exists(DEFAULT), reason="text model not bundled")


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return f.read()


def test_model_loads(settings):
    assert TextModel(settings).ready()


async def test_machine_written_story_leans_synthetic(settings, index):
    pipe = Pipeline(settings, index, providers=[TextModel(settings)])
    v = await pipe.text(fixture("gpt_wp.txt"), "test", "share", "d")
    assert v.tier in ("leaning_synthetic", "likely_synthetic")
    assert any("our text model" in e for e in v.evidence)


async def test_human_story_leans_human(settings, index):
    pipe = Pipeline(settings, index, providers=[TextModel(settings)])
    v = await pipe.text(fixture("human_wp.txt"), "test", "share", "d")
    assert v.tier in ("leaning_human", "no_ai_signals")


async def test_short_text_gets_low_weight(settings, index):
    pipe = Pipeline(settings, index, providers=[TextModel(settings)])
    short = " ".join(fixture("gpt_wp.txt").split()[:45])
    v = await pipe.text(short, "test", "share", "d")
    sig = [s for s in v.signals if s.name == "squint_text"][0]
    assert sig.reliability <= 0.25
