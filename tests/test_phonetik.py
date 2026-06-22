from app.tools.phonetik import koelner_phonetik


def test_stefan_stephan_steffen_collide():
    code = koelner_phonetik("stefan")
    assert koelner_phonetik("stephan") == code
    assert koelner_phonetik("steffen") == code


def test_umlaut_baer_equals_bar():
    assert koelner_phonetik("Bär") == koelner_phonetik("Baer")
    assert koelner_phonetik("Bär") == koelner_phonetik("Bar")


def test_mueller_variants_collide():
    assert koelner_phonetik("Müller") == koelner_phonetik("Mueller")


def test_distinct_names_differ():
    assert koelner_phonetik("Schindler") != koelner_phonetik("Stefan")


def test_empty_string():
    assert koelner_phonetik("") == ""
