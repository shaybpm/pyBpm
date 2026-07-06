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
  - FILTER SET (decision D6): the selected discipline-filter id set is part of
    the validity key. Scores depend on which discipline filters define the
    reference systems, so a changed selection must reset the cache - otherwise
    the grid would show scores computed with the old disciplines. The ids are
    stored as a sorted list; any mismatch drops the whole entry. Pre-D6 cache
    entries (no filter_ids field) therefore invalidate on the first D6 read.
  - FALLBACK: a daily date stamp - a new day invalidates the entry too, so
    planner-side model changes (which don't change the comp version) are picked
    up at least once a day (and any time via the Recompute buttons).

Only the score fields are cached; "exists" and "sheet" are always derived live.
Empty sections (0 reference systems) are cached as normal, displayable records
with n=0 (decision D7) - the caller synthesizes that record. A transient failure
is NOT cached (retried next visit). The legacy {"skipped": True} marker (and
put_skipped) is retained for back-compat but no longer written by the live path.
IronPython 2.7. """

from System import DateTime

from LocalUserInputs import LocalUserInputs
import RevitUtils

CACHE_FILE = "get_bpm_sections_scores_cache"

# S1: "systems" is a list of per-reference-system dicts
# ({id, category, overlap, points, failed}) feeding the details panel. It is a
# JSON-serializable list of primitives, so put() copies it like the scalar
# fields. Records written before S1 lack it; the details-panel consumer treats a
# missing "systems" as "needs recompute" (no cache-key change).
_RESULT_FIELDS = [
    "section_name",
    "section_id",
    "lower",
    "upper",
    "n",
    "failed",
    "systems",
]


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
    def __init__(self, doc, comp_doc, filter_ids=None):
        self.version_guid, self.num_of_saves = get_comp_version(comp_doc)
        self.today = _today()
        # D6: the discipline-filter id set participates in the validity key.
        self.filter_key = self._normalize_filter_ids(filter_ids)
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

    @staticmethod
    def _normalize_filter_ids(filter_ids):
        """Stable, order-independent representation of the selected filter id set
        for the validity key. None (no selection given) stays None."""
        if filter_ids is None:
            return None
        return sorted(int(fid) for fid in filter_ids)

    def _fresh_entry(self):
        return {
            "version_guid": self.version_guid,
            "num_of_saves": self.num_of_saves,
            "date": self.today,
            "filter_ids": self.filter_key,
            "sections": {},  # str(section_id) -> result dict (empties: n=0 record)
        }

    def _is_valid(self, entry):
        if not entry:
            return False
        if entry.get("version_guid") != self.version_guid:
            return False
        if entry.get("date") != self.today:
            return False
        if entry.get("filter_ids") != self.filter_key:
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
        self.entry["filter_ids"] = self.filter_key
        self._store.data[self.key] = self.entry
        self._store.save_inputs()
