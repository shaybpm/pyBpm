# -*- coding: utf-8 -*-
""" DirectContext3D single-instance display for Get Bpm Sections (S3).

Highlights ONE reference system's solids (from the compilation model) inside the
planner's host section view, as a semi-transparent overlay, and zooms to it.

Single-owner, single-instance by design (section 6, the highest risk of this
feature - a leaked dc3d server keeps drawing forever):
  - A FIXED module-level server GUID: add_server() removes any leftover server
    with the same GUID, so only ONE server can ever be registered. Never
    generate a new GUID.
  - The server is created with register=False; show/clear use the ViewRange safe
    swap (remove_server -> set meshes -> add_server) so the Draw Thread never
    calls GetBoundingBox mid-transition.
  - EVERY method here runs on the Revit API context (called from the window's
    External Event), except shutdown() which only unregisters the server (a
    service-registry op, safe outside a transaction) on window close.

Geometry: comp elements are read with get_Geometry and transformed into the host
coordinate space by the comp link's total transform (get_solids_from_element is
ported from DEV RevitUtils - pyBpm RevitUtils only has the single-solid version).
IronPython 2.7. """

import os, sys

from System import Guid
from Autodesk.Revit.DB import (
    XYZ,
    Solid,
    SolidUtils,
    Options,
    ColorWithTransparency,
)

from pyrevit.revit import dc3dserver

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))

import RevitUtils  # extension-level lib
import SectionsCreate as creator  # type: ignore

# FIXED server GUID - guarantees only one server is ever registered (add_server
# removes a leftover with the same id). Do NOT replace with Guid.NewGuid().
SERVER_GUID = Guid("b7e2c1a4-3f5d-4e8a-9c2b-1a2b3c4d5e6f")

# Semi-transparent cyan (r, g, b, transparency) - transparency 0=opaque..255=clear.
DISPLAY_COLOR = ColorWithTransparency(0, 200, 255, 110)


def _get_solids_from_geometry_element(geometry_element, transform=None):
    """All non-empty solids in a GeometryElement (recursing into instances),
    optionally transformed. Ported from DEV RevitUtils (the many-solids variant
    the pyBpm lib lacks)."""
    solids = []
    for geo in geometry_element:
        if isinstance(geo, Solid):
            if geo.Volume == 0:
                continue
            if transform is not None:
                geo = SolidUtils.CreateTransformed(geo, transform)
            solids.append(geo)
        elif hasattr(geo, "GetInstanceGeometry"):
            inst_geo = geo.GetInstanceGeometry()
            solids.extend(_get_solids_from_geometry_element(inst_geo, transform))
    return solids


def _get_solids_from_element(element, transform=None):
    options = Options()
    geometry_element = element.get_Geometry(options)
    if geometry_element is None:
        return []
    return _get_solids_from_geometry_element(geometry_element, transform)


class SectionsDisplay(object):
    """Single-owner dc3d server, held by the results window (created lazily).

    show_system / clear run on the Revit API context (via the window's External
    Event). shutdown runs on window close (UI thread) - only unregisters."""

    def __init__(self, uidoc, comp_doc, comp_link):
        self.uidoc = uidoc
        self.comp_doc = comp_doc
        self.comp_link = comp_link
        self._server = None
        self.current_system_id = None

    def _ensure_server(self):
        if self._server is None:
            self._server = dc3dserver.Server(
                guid=SERVER_GUID, uidoc=self.uidoc, register=False
            )
        return self._server

    def show_system(self, uiapp, system_id, section_name):
        """Draw the given comp element's solids in the host section view and zoom,
        replacing any currently-shown system (safe swap).

        If the new system produces nothing to draw (element gone / no solids / no
        meshes), CLEAR the previous drawing rather than leaving it on screen - the
        caller switches system by calling this directly (no preceding hide), so a
        silent early-return would leave the old overlay drawn while the UI claims
        the new one is shown (D8)."""
        server = self._ensure_server()
        meshes = self._build_meshes(system_id)
        if not meshes:
            self.clear(uiapp)
            return
        # Safe swap (ViewRange pattern): remove -> set -> add.
        try:
            server.remove_server()
        except Exception:
            pass
        server.meshes = meshes
        try:
            server.add_server()
        except Exception:
            pass
        self.current_system_id = int(system_id)
        self._zoom_to(uiapp, section_name, meshes)

    def _build_meshes(self, system_id):
        """The display meshes for a comp system id (host coords), or [] if the
        element is gone / has no solids / triangulation yields nothing."""
        try:
            comp_el = self.comp_doc.GetElement(
                RevitUtils.getElementId(self.comp_doc, int(system_id))
            )
        except Exception:
            comp_el = None
        if comp_el is None or not comp_el.IsValidObject:
            return []
        transform = self.comp_link.GetTotalTransform()
        solids = _get_solids_from_element(comp_el, transform)
        if not solids:
            return []
        host_doc = self.uidoc.Document
        meshes = []
        for solid in solids:
            # doc is only used for material lookup, bypassed because a color is
            # forced - so host_doc is fine. from_solid returns None on a bad face.
            mesh = dc3dserver.Mesh.from_solid(host_doc, solid, DISPLAY_COLOR)
            if mesh is not None:
                meshes.append(mesh)
        return meshes

    def _zoom_to(self, uiapp, section_name, meshes):
        """Activate the host section view (D2 - it exists) and zoom to the meshes'
        bounds. Everything best-effort - a zoom failure must not break display."""
        uidoc = uiapp.ActiveUIDocument
        host_doc = uidoc.Document
        host_view = creator.find_existing_section(host_doc, section_name)
        if host_view is None:
            try:
                uidoc.RefreshActiveView()
            except Exception:
                pass
            return
        try:
            if uidoc.ActiveView is None or uidoc.ActiveView.Id != host_view.Id:
                uidoc.ActiveView = host_view
        except Exception:
            pass
        min_p, max_p = self._mesh_bounds(meshes)
        if min_p is not None:
            try:
                for uiview in uidoc.GetOpenUIViews():
                    if uiview.ViewId == host_view.Id:
                        uiview.ZoomAndCenterRectangle(min_p, max_p)
                        break
            except Exception:
                pass
        try:
            uidoc.RefreshActiveView()
        except Exception:
            pass

    def _mesh_bounds(self, meshes):
        xs = []
        ys = []
        zs = []
        for mesh in meshes:
            for v in mesh.vertices:
                xs.append(v.X)
                ys.append(v.Y)
                zs.append(v.Z)
        if not xs:
            return None, None
        return (
            XYZ(min(xs), min(ys), min(zs)),
            XYZ(max(xs), max(ys), max(zs)),
        )

    def clear(self, uiapp=None):
        """Remove the drawing (safe swap to empty) and refresh. current_system_id
        is reset. uiapp is used only for the view refresh (None on shutdown)."""
        if self._server is not None:
            try:
                self._server.remove_server()
            except Exception:
                pass
            try:
                self._server.meshes = []
            except Exception:
                pass
        self.current_system_id = None
        if uiapp is not None:
            try:
                uiapp.ActiveUIDocument.RefreshActiveView()
            except Exception:
                pass

    def shutdown(self):
        """Window-close cleanup: unregister the server for good (registry op,
        safe off the API context). No view refresh - the window is closing."""
        self.clear(None)
        if self._server is not None:
            try:
                self._server.remove_server()
            except Exception:
                pass
