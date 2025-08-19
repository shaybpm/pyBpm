# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from pyrevit.framework import wpf
import os

from SRI_DialogResults import SRI_DialogResults
from SRI_OneSourceModelPage import SRI_OneSourceModelPage
from SRI_MultipleSourceModelsPage import SRI_MultipleSourceModelsPage

xaml_file = os.path.join(os.path.dirname(__file__), "SRI_PreDialog.xaml")


class SRI_PreDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)
        self.doc = doc
        self.dialog_results = SRI_DialogResults(doc)

        self.sources_link_result = None

        self.one_source_model_page = SRI_OneSourceModelPage(self.dialog_results)
        self.multiple_source_models_page = SRI_MultipleSourceModelsPage(
            self.dialog_results
        )
        
        # IMPORTANT: Set the callback function after initializing the pages
        self.dialog_results.cb_func = self.dialog_results_callback

        if len(self.dialog_results.sources) <= 1:
            self.MainFrame.Navigate(self.one_source_model_page)
        else:
            self.MainFrame.Navigate(self.multiple_source_models_page)
            
        self.initialize_enabled()

    def initialize_enabled(self):
        sources = self.dialog_results.sources
        self.oneSourceModelButton.IsEnabled = len(sources) <= 1
        self.ok_btn.IsEnabled = len(sources) > 0

    def dialog_results_callback(self, sources, reservoir):
        self.initialize_enabled()
        self.one_source_model_page.dialog_results_callback(sources, reservoir)
        self.multiple_source_models_page.dialog_results_callback(sources, reservoir)

    def MainFrame_Navigated(self, sender, e):
        if isinstance(e.Content, SRI_OneSourceModelPage):
            self.oneSourceModelButton.Background = Windows.Media.Brushes.LightBlue
            self.multipleSourceModelsButton.Background = (
                Windows.Media.Brushes.Transparent
            )
        elif isinstance(e.Content, SRI_MultipleSourceModelsPage):
            self.oneSourceModelButton.Background = Windows.Media.Brushes.Transparent
            self.multipleSourceModelsButton.Background = Windows.Media.Brushes.LightBlue

    def oneSourceModelButton_click(self, sender, e):
        self.MainFrame.Navigate(self.one_source_model_page)

    def multipleSourceModelsButton_click(self, sender, e):
        self.MainFrame.Navigate(self.multiple_source_models_page)

    def ok_btn_click(self, sender, e):
        self.dialog_results.save_models()
        self.sources_link_result = [item.link for item in self.dialog_results.sources]
        self.Close()

    def cancel_btn_click(self, sender, e):
        self.Close()
