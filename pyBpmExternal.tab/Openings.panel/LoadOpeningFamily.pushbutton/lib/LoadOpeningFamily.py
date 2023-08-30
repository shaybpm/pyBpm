import os

from Autodesk.Revit.DB import Transaction

# ------------------------------------------------------------

def run(doc):
    t = Transaction(doc, 'BPM | Load Opening Family')
    t.Start()

    # Load the family
    family_rec_filename = "M_Rectangular Face Opening Solid.rfa"
    family_rec_path = os.path.join(os.path.dirname(__file__), family_rec_filename)
    family_round_filename = "M_Round Face Opening Solid.rfa"
    family_round_path = os.path.join(os.path.dirname(__file__), family_round_filename)

    doc.LoadFamily(family_rec_path)
    doc.LoadFamily(family_round_path)

    t.Commit()
