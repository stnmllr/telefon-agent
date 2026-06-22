import glob
import os
import yaml

_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "playbooks")
_REQUIRED = {"id", "title", "area", "trigger", "diagnose",
             "loesung", "verifikation", "eskalation", "handbuch_refs"}
_AREAS = {"FIBU", "ERP", "EVS", "HR", "IT", "Verwaltung"}


def _playbook_entries():
    for path in glob.glob(os.path.join(_DIR, "*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, list), f"{path}: muss eine Liste sein"
        for entry in data:
            yield path, entry


def test_at_least_one_playbook_exists():
    assert list(_playbook_entries()), "kein Playbook gefunden"


def test_required_fields_present():
    for path, entry in _playbook_entries():
        missing = _REQUIRED - set(entry.keys())
        assert not missing, f"{path}: fehlende Felder {missing}"


def test_area_valid():
    for path, entry in _playbook_entries():
        assert entry["area"] in _AREAS, f"{path}: ungültige area {entry['area']}"


def test_eskalation_has_bedingung_and_aktion():
    for path, entry in _playbook_entries():
        for esk in entry["eskalation"]:
            assert "bedingung" in esk and "aktion" in esk, f"{path}: eskalation unvollständig"
