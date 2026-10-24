from squint.crop import find_media, region_kind
from conftest import noisy_photo, phone_screenshot, text_screenshot


def test_finds_photo_inside_instagram_like_screenshot():
    shot, truth = phone_screenshot(noisy_photo(5))
    box, conf, _ = find_media(shot)
    assert abs(box[1] - truth[1]) < 40
    assert abs(box[3] - truth[3]) < 40
    assert box[0] < 20 and box[2] > shot.size[0] - 20
    assert conf > 0.6


def test_hint_wins_when_present():
    shot, _ = phone_screenshot(noisy_photo(5))
    box, conf, _ = find_media(shot, hint=(10, 300, 1000, 1300))
    assert box == (10, 300, 1000, 1300)
    assert conf > 0.9


def test_letterboxed_reel():
    from PIL import Image
    shot = Image.new("RGB", (1080, 2340), "black")
    photo = noisy_photo(7, (1080, 1400))
    shot.paste(photo, (0, 470))
    box, _, _ = find_media(shot)
    assert abs(box[1] - 470) < 30
    assert abs(box[3] - 1870) < 30


def test_region_kind_separates_text_and_photo():
    assert region_kind(noisy_photo(1)) == "photo"
    shot = text_screenshot(["hello there this is an email about your account"] * 20)
    assert region_kind(shot.crop((0, 200, 1080, 1200))) == "text"
