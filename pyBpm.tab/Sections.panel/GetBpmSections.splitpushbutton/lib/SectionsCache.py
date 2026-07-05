# -*- coding: utf-8 -*-
""" Local persistent cache for Get Bpm Sections match scores (Phase 5).

Scores are expensive (boolean-op volume intersections over every section), so
they are cached in a per-user local file (via LocalUserInputs -> get_data_file,
persists across Revit sessions), keyed by (this modelGuid, comp modelGuid).

Invalidation (section 4.7 / R2-5):
  - PRIMARY: the loaded comp document's version. We store
    Document.GetDocumentVersion(comp_doc).VersionGUID (+ NumberOfSaves); if the
    current comp VersionGUID differs, the whole cache entry is dropped and
    everything recomputes - this precisely detects a coordinator resync of the
    loaded link.
  - FALLBACK: a daily date stamp - a new day invalidates the entry too, so
    planner-side model changes (which don't change the comp version) are picked
    up at least once a day (and any time via the Recompute buttons).

Only the score fields are cached; "exists" and "sheet" are always derived live.
Empty/failed sections are cached as a {"skipped": True} marker so they are not
recomputed on every open. IronPython 2.7. """

from System import DateTime

from LocalUserInputs import LocalUserInputs
import RevitUtils

CACHE_FILE = "get_bpm_sections_scores_cache"

_RESULT_FIELDS = ["section_name", "section_id", "lower", "upper", "n", "failed"]


def _today():
    d = DateTime.Today
    return "{:04d}-{:02d}-{:02d}".format(d.Year, d.Month, d.Day)


def get_comp_version(comp_doc):
    """(version_guid, num_of_saves) of the loaded comp doc, or (None, None) if
    the API is unavailable (older Revit) - then only the daily stamp applies."""
    try:
        from Autodesk.Revit.DB import Document

        doc_version = Document.GetDocumentVersion(comp_doc)
        if doc_version is None:
            return None, None
        return doc_version.VersionGUID.ToString(), doc_version.NumberOfSaves
    except:
        return None, None


class SectionsScoreCache:
    def __init__(self, doc, comp_doc):
        self.version_guid, self.num_of_saves = get_comp_version(comp_doc)
        self.today = _today()
        self.key = (
            RevitUtils.get_model_info(doc)["modelGuid"]
            + "__"
            + RevitUtils.get_model_info(comp_doc)["modelGuid"]
        )
        self._store = LocalUserInputs(CACHE_FILE)
        entry = self._store.data.get(self.key)
        if not self._is_valid(entry):
            entry = self._fresh_entry()
        self.entry = entry

    def _fresh_entry(self):
        return {
            "version_guid": self.version_guid,
            "num_of_saves": self.num_of_saves,
            "date": self.today,
            "sections": {},  # str(section_id) -> result dict or {"skipped": True}
        }

    def _is_valid(self, entry):
        if not entry:
            return False
        if entry.get("version_guid") != self.version_guid:
            return False
        if entry.get("date") != self.today:
            return False
        return True

    def get(self, section_id):
        """Cached record for a section id: a result dict, a {"skipped": True}
        marker, or None if not cached."""
        return self.entry["sections"].get(str(section_id))

    def put(self, result):
        self.entry["sections"][str(result["section_id"])] = dict(
            (field, result[field]) for field in _RESULT_FIELDS
        )

    def put_skipped(self, section_id):
        self.entry["sections"][str(section_id)] = {"skipped": True}

    def save(self):
        self.entry["version_guid"] = self.version_guid
        self.entry["num_of_saves"] = self.num_of_saves
        self.entry["date"] = self.today
        self._store.data[self.key] = self.entry
        self._store.save_inputs()
