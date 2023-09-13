import os

from Autodesk.Revit.DB import Transaction, FilteredElementCollector, Family

from pyrevit import script

# ------------------------------------------------------------


def run(doc):
    output = script.get_output()
    output.print_html("<h1>Load Opening Families</h1>")

    t = Transaction(doc, "BPM | Load Opening Family")
    t.Start()

    # Family paths
    family_rec_name = "M_Rectangular Face Opening Solid"
    family_rec_filename = family_rec_name + ".rfa"
    family_rec_path = os.path.join(os.path.dirname(__file__), family_rec_filename)
    family_round_name = "M_Round Face Opening Solid"
    family_round_filename = family_round_name + ".rfa"
    family_round_path = os.path.join(os.path.dirname(__file__), family_round_filename)

    # Check if the family is already loaded
    family_rec_loaded = False
    family_round_loaded = False
    families = FilteredElementCollector(doc).OfClass(Family)
    for family in families:
        if family.Name == family_rec_name:
            family_rec_loaded = True
        if family.Name == family_round_name:
            family_round_loaded = True

    # Load the family if it's not loaded
    load_family_rec_result = None
    load_family_round_result = None
    if not family_rec_loaded:
        load_family_rec_result = doc.LoadFamily(family_rec_path)
    else:
        output.print_html(
            '<div style="color:yellow">Family already loaded: '
            + family_rec_name
            + "</div>"
        )
    if not family_round_loaded:
        load_family_round_result = doc.LoadFamily(family_round_path)
    else:
        output.print_html(
            '<div style="color:yellow">Family already loaded: '
            + family_round_name
            + "</div>"
        )

    if not load_family_rec_result or not load_family_round_result:
        output.print_html(
            '<div style="color:blue">If you want to reload the family, you need to change the name of the family that already loaded, or remove it from the project.</div>'
        )

    # Print the results
    if load_family_rec_result:
        output.print_html(
            '<div style="color:green">Loaded family: ' + family_rec_filename + "</div>"
        )
    if load_family_round_result:
        output.print_html(
            '<div style="color:green">Loaded family: '
            + family_round_filename
            + "</div>"
        )

    t.Commit()
