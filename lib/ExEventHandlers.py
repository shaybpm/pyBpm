# -*- coding: utf-8 -*-

from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent
from Autodesk.Revit.Exceptions import InvalidOperationException


class SimpleEventHandler(IExternalEventHandler):
    def __init__(self, execute_func):
        self.execute_func = execute_func

    def Execute(self, uiapp):
        try:
            self.execute_func(uiapp)
        except InvalidOperationException:
            print("InvalidOperationException catched")

    def GetName(self):
        return "Function executed by an IExternalEventHandler in a Form"


def get_simple_external_event(execute_func):
    simple_event_handler = SimpleEventHandler(execute_func)
    return ExternalEvent.Create(simple_event_handler)
