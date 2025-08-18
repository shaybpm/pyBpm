# -*- coding: utf-8 -*-

from SRI_PreDialog import SRI_PreDialog

def ask_for_source_models(doc):
    dialog = SRI_PreDialog(doc)
    dialog.ShowDialog()
    return dialog.sources_link_result

def main(doc):
    if not doc.IsModelInCloud:
        return
    
    source_models = ask_for_source_models(doc)
    if not source_models:
        return
    print(source_models)
