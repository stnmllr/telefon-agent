"""Tests für den Pure-Logic-Kern des KB-Konvertierungs-Tools (kb_convert.core)."""

from kb_convert import core


class TestSlugify:
    def test_simple_spaces_to_dashes_lowercase(self):
        assert core.slugify("Handbuch Fibu") == "handbuch-fibu"

    def test_keeps_internal_hyphen(self):
        assert core.slugify("Handbuch Buchungs-Bsp") == "handbuch-buchungs-bsp"

    def test_umlaut_and_underscore(self):
        assert core.slugify("Handbuchergänzung_Schweiz") == "handbuchergaenzung-schweiz"

    def test_digits_kept(self):
        assert core.slugify("MWSt 2024 Schweiz") == "mwst-2024-schweiz"

    def test_dots_become_dashes(self):
        assert core.slugify("enventa.ebilanz_hinweise") == "enventa-ebilanz-hinweise"

    def test_no_leading_trailing_or_double_dashes(self):
        assert core.slugify("  Handbuch   ABI  ") == "handbuch-abi"


class TestIsProbablyScanned:
    def test_real_text_layer_not_scanned(self):
        # 89107 Zeichen / 46 Seiten = 1937 Z./Seite
        assert core.is_probably_scanned(89107, 46) is False

    def test_below_threshold_is_scanned(self):
        assert core.is_probably_scanned(50, 1) is True

    def test_zero_chars_is_scanned(self):
        assert core.is_probably_scanned(0, 5) is True

    def test_threshold_boundary_exactly_100_not_scanned(self):
        assert core.is_probably_scanned(100, 1) is False

    def test_just_below_threshold_is_scanned(self):
        assert core.is_probably_scanned(99, 1) is True

    def test_zero_pages_is_scanned(self):
        assert core.is_probably_scanned(0, 0) is True


class TestIsPageNumberLine:
    def test_bare_number(self):
        assert core.is_page_number_line("12") is True

    def test_dashed_number(self):
        assert core.is_page_number_line("- 12 -") is True

    def test_seite_n(self):
        assert core.is_page_number_line("Seite 5") is True

    def test_seite_n_von_m(self):
        assert core.is_page_number_line("Seite 5 von 20") is True

    def test_n_slash_m(self):
        assert core.is_page_number_line("12 / 20") is True

    def test_content_with_number_kept(self):
        assert core.is_page_number_line("Kapitel 3 Buchungen") is False

    def test_label_with_number_kept(self):
        assert core.is_page_number_line("Buchung 100") is False


class TestStripBoilerplate:
    def test_removes_header_repeated_on_all_pages(self):
        pages = [
            "syska ProFI\nInhalt Seite eins\nmehr Text",
            "syska ProFI\nInhalt Seite zwei\nnoch mehr",
            "syska ProFI\nInhalt Seite drei\nund Schluss",
        ]
        out = core.strip_boilerplate(pages)
        assert "syska ProFI" not in out
        assert "Inhalt Seite eins" in out
        assert "Inhalt Seite drei" in out

    def test_removes_pure_page_number_lines(self):
        pages = [
            "Echter Inhalt A\n- 1 -",
            "Echter Inhalt B\n- 2 -",
            "Echter Inhalt C\n- 3 -",
        ]
        out = core.strip_boilerplate(pages)
        assert "- 1 -" not in out
        assert "- 2 -" not in out
        assert "Echter Inhalt B" in out

    def test_keeps_lines_that_appear_only_once(self):
        pages = [
            "Einzigartiger Absatz eins\nGemeinsame Fußzeile",
            "Anderer Absatz zwei\nGemeinsame Fußzeile",
            "Dritter Absatz drei\nGemeinsame Fußzeile",
        ]
        out = core.strip_boilerplate(pages)
        assert "Einzigartiger Absatz eins" in out
        assert "Gemeinsame Fußzeile" not in out  # auf allen Seiten -> Boilerplate

    def test_few_pages_only_strips_page_numbers_not_repeats(self):
        # Bei < 3 Seiten ist Wiederholungs-Erkennung unzuverlässig -> roh lassen
        pages = [
            "Kopf\nInhalt eins\n- 1 -",
            "Kopf\nInhalt zwei\n- 2 -",
        ]
        out = core.strip_boilerplate(pages)
        assert "Kopf" in out          # Wiederholung NICHT entfernt (zu wenige Seiten)
        assert "- 1 -" not in out     # Seitenzahl trotzdem entfernt


class TestBuildReport:
    def _rows(self):
        return [
            {"name": "Handbuch Fibu.pdf", "pages": 200, "chars": 400000,
             "md_bytes": 410000, "scanned": False},
            {"name": "Handbuch Rebu.pdf", "pages": 46, "chars": 89107,
             "md_bytes": 89716, "scanned": False},
        ]

    def test_contains_table_header_and_rows(self):
        out = core.build_report(self._rows())
        assert "| Datei |" in out
        assert "Handbuch Fibu.pdf" in out
        assert "Handbuch Rebu.pdf" in out

    def test_contains_sum_row_and_under_limit_note(self):
        out = core.build_report(self._rows())
        assert "Gesamt" in out
        assert "20 MB" in out
        # Summe ~0.5 MB << 20 MB -> als unter Limit markiert
        assert "unter" in out.lower()

    def test_flags_scanned_files(self):
        rows = [{"name": "Scan.pdf", "pages": 10, "chars": 200,
                 "md_bytes": 250, "scanned": True}]
        out = core.build_report(rows)
        assert "ja" in out.lower()  # gescannt? -> ja
