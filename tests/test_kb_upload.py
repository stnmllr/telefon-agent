"""Tests für den Pure-Logic-Kern des KB-Upload-Tools (kb_upload.core)."""

from kb_upload import core


class TestDocumentName:
    def test_basic_handbook(self):
        assert core.document_name("handbuch-fibu.md") == "FIBU – Handbuch Fibu"

    def test_with_year(self):
        assert core.document_name("mwst-2024-schweiz.md") == "FIBU – Mwst 2024 Schweiz"

    def test_ignores_subdir_prefix(self):
        assert core.document_name("optional/handbuch-gdpdu.md") == "FIBU – Handbuch Gdpdu"


class TestSelectPending:
    def test_skips_already_uploaded(self):
        files = ["a.md", "b.md", "c.md"]
        manifest = {"a.md": {"id": "x"}}
        assert core.select_pending(files, manifest, force=False) == ["b.md", "c.md"]

    def test_empty_manifest_returns_all(self):
        files = ["a.md", "b.md"]
        assert core.select_pending(files, {}, force=False) == ["a.md", "b.md"]

    def test_force_returns_all(self):
        files = ["a.md", "b.md"]
        manifest = {"a.md": {"id": "x"}, "b.md": {"id": "y"}}
        assert core.select_pending(files, manifest, force=True) == ["a.md", "b.md"]


class TestMergeManifest:
    def test_adds_new_entry(self):
        manifest = {"a.md": {"id": "x", "name": "A"}}
        out = core.merge_manifest(manifest, "b.md", {"id": "y", "name": "B"})
        assert out["a.md"] == {"id": "x", "name": "A"}
        assert out["b.md"] == {"id": "y", "name": "B"}

    def test_overwrites_existing_on_reupload(self):
        manifest = {"a.md": {"id": "old"}}
        out = core.merge_manifest(manifest, "a.md", {"id": "new"})
        assert out["a.md"] == {"id": "new"}

    def test_does_not_mutate_input(self):
        manifest = {"a.md": {"id": "x"}}
        core.merge_manifest(manifest, "b.md", {"id": "y"})
        assert "b.md" not in manifest
