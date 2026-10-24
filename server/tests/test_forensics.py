from squint import forensics
from conftest import noisy_photo, png_with_text, jpeg_with_app, to_bytes


def test_sd_parameters_chunk_is_caught():
    data = png_with_text(noisy_photo(2), "parameters", "a cat, Steps: 20, Sampler: DPM++ 2M, Model: sd_xl_base")
    m = forensics.metadata_scan(data)
    assert m["generator"] == "stable diffusion"
    assert any("prompt block" in n for n in m["notes"])


def test_midjourney_in_exif_software():
    exif = b"Exif\x00\x00" + b"Software\x00" + b"Midjourney v6\x00"
    data = jpeg_with_app(noisy_photo(2), 0xE1, exif)
    m = forensics.metadata_scan(data)
    assert m["generator"] == "midjourney"


def test_iptc_trained_algorithmic_media():
    xmp = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta><rdf:Description Iptc4xmpExt:DigitalSourceType=\"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia\"/></x:xmpmeta>"
    data = jpeg_with_app(noisy_photo(2), 0xE1, xmp)
    m = forensics.metadata_scan(data)
    assert m["source_type"] == "trainedalgorithmicmedia"
    sigs, _ = forensics.inspect_image(data, noisy_photo(2))
    assert any(n == "metadata" and s > 0.9 for n, s, _, _ in sigs)


def test_c2pa_camera_capture_reads_as_provenance():
    jumbf = b"\x00\x00\x00\x40jumbc2pa\x00c2pa.actions digitalSourceType digitalCapture claim_generator Leica Camera AG"
    exif = b"Exif\x00\x00Make\x00Leica\x00Software\x00Leica M11 firmware\x00"
    data = jpeg_with_app(noisy_photo(2), 0xE1, exif)
    data = jpeg_with_app(data, 0xEB, jumbf)
    m = forensics.metadata_scan(data)
    assert m["c2pa"] and m["camera"]
    sigs, _ = forensics.inspect_image(data, noisy_photo(2))
    prov = [s for s in sigs if s[0] == "provenance"]
    assert prov and prov[0][1] <= 0.1


def test_plain_photo_has_no_generator():
    data = to_bytes(noisy_photo(2), "JPEG", quality=80)
    m = forensics.metadata_scan(data)
    assert m["generator"] == ""
    assert not m["c2pa"]


def test_spectral_and_residual_in_range():
    img = noisy_photo(2)
    s, note = forensics.spectral_score(img)
    assert 0 < s < 1 and note
    s, note = forensics.residual_score(img)
    assert 0 < s < 1 and note


def test_jpeg_quality_estimate():
    hi = to_bytes(noisy_photo(2), "JPEG", quality=98)
    lo = to_bytes(noisy_photo(2), "JPEG", quality=50)
    assert forensics._jpeg_quant_quality(hi) >= 95
    assert forensics._jpeg_quant_quality(lo) <= 80
