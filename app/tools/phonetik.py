"""Kölner Phonetik (Cologne phonetics) — deutsches Soundex-Äquivalent.

Gruppiert STT-Misshears wie Stefan/Stephan/Steffen als phonetisch gleich.
Reine stdlib, kein I/O.
"""
import unicodedata

_VOWELS = set("aeijouy")
_UMLAUT_MAP = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss",
               "é": "e", "è": "e", "ê": "e", "â": "a", "ç": "c"}


def _preprocess(s: str) -> str:
    s = unicodedata.normalize("NFC", s).casefold()
    s = "".join(_UMLAUT_MAP.get(c, c) for c in s)
    return "".join(c for c in s if c.isalpha())


def koelner_phonetik(text: str) -> str:
    s = _preprocess(text)
    n = len(s)
    codes = []
    for i, c in enumerate(s):
        prev = s[i - 1] if i > 0 else ""
        nxt = s[i + 1] if i + 1 < n else ""
        if c in _VOWELS:
            code = "0"
        elif c == "b":
            code = "1"
        elif c == "p":
            code = "3" if nxt == "h" else "1"
        elif c in "dt":
            code = "8" if nxt in "csz" else "2"
        elif c in "fvw":
            code = "3"
        elif c in "gkq":
            code = "4"
        elif c == "c":
            if i == 0:
                code = "8" if nxt in "ahkloqrux" else "4"
            else:
                code = "8" if (prev in "sz" or nxt not in "ahkoqux") else "4"
        elif c == "x":
            code = "48"
        elif c == "l":
            code = "5"
        elif c in "mn":
            code = "6"
        elif c == "r":
            code = "7"
        elif c in "sz":
            code = "8"
        else:  # h und alles andere → kein Code
            code = ""
        codes.append(code)
    raw = "".join(codes)
    collapsed = []
    for ch in raw:
        if not collapsed or collapsed[-1] != ch:
            collapsed.append(ch)
    res = "".join(collapsed)
    if res:
        res = res[0] + res[1:].replace("0", "")
    return res
