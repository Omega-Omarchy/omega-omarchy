from omega_omarchy.accessibility import Accessibility, DEFAULT_KEYBOARD


def test_remap_and_independent_crt():
    a11y = Accessibility()
    a11y.remap("jump", "W")
    assert a11y.keyboard["jump"] == "W"
    assert DEFAULT_KEYBOARD["jump"] == "Z"
    a11y.crt["scanlines"] = 0.8
    a11y.crt["enabled"] = 1.0
    a11y.reduced_motion = True
    rec = a11y.to_record()
    assert rec["keyboard"]["jump"] == "W"
    assert rec["reducedMotion"] is True
    assert rec["crt"]["bloom"] == 0.0
    assert rec["subtitle"] is True
