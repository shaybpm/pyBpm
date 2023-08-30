from Autodesk.Revit.DB import Transaction

# ------------------------------------------------------------

def run(doc):
    print("hi")
    
    t = Transaction(doc, 'BPM | Load Opening Family')
    t.Start()

    # Load the family
    family_rec_path = "M_Rectangular Face Opening Solid.rfa"
    family_round_path = "M_Round Face Opening Solid.rfa"

    t.Commit()
