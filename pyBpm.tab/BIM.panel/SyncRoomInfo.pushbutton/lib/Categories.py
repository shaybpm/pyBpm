# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import BuiltInCategory

category_names = [
    "Air Systems",
    "Air Terminals",
    "Audio Visual Devices",
    "Communication Devices",
    "Data Devices",
    "Duct Accessories",
    "Electrical Circuits",
    "Electrical Equipment",
    "Electrical Fixtures",
    "Fire Alarm Devices",
    "Fire Protection",
    "Food Service Equipment",
    "Lighting Devices",
    "Lighting Fixtures",
    "Mechanical Control Devices",
    "Mechanical Equipment",
    "Mechanical Equipment Sets",
    "Medical Equipment",
    "Nurse Call Devices",
    "Pipe Accessories",
    "Plumbing Equipment",
    "Plumbing Fixtures",
    "Security Devices",
    "Specialty Equipment",
    "Sprinklers",
    "Telephone Devices",
    "Wires",
    "Zone Equipment",
]

built_in_categories = [
    BuiltInCategory.OST_MEPAnalyticalAirLoop,  # Air Systems
    BuiltInCategory.OST_DuctTerminal,  # Air Terminals
    BuiltInCategory.OST_AudioVisualDevices,  # Audio Visual Devices
    BuiltInCategory.OST_CommunicationDevices,  # Communication Devices
    BuiltInCategory.OST_DataDevices,  # Data Devices
    BuiltInCategory.OST_DuctAccessory,  # Duct Accessories
    BuiltInCategory.OST_ElectricalCircuit,  # Electrical Circuits
    BuiltInCategory.OST_ElectricalEquipment,  # Electrical Equipment
    BuiltInCategory.OST_ElectricalFixtures,  # Electrical Fixtures
    BuiltInCategory.OST_FireAlarmDevices,  # Fire Alarm Devices
    BuiltInCategory.OST_FireProtection,  # Fire Protection
    BuiltInCategory.OST_FoodServiceEquipment,  # Food Service Equipment
    BuiltInCategory.OST_LightingDevices,  # Lighting Devices
    BuiltInCategory.OST_LightingFixtures,  # Lighting Fixtures
    BuiltInCategory.OST_MechanicalControlDevices,  # Mechanical Control Devices
    BuiltInCategory.OST_MechanicalEquipment,  # Mechanical Equipment
    BuiltInCategory.OST_MechanicalEquipmentSet,  # Mechanical Equipment Sets
    BuiltInCategory.OST_MedicalEquipment,  # Medical Equipment
    BuiltInCategory.OST_NurseCallDevices,  # Nurse Call Devices
    BuiltInCategory.OST_PipeAccessory,  # Pipe Accessories
    BuiltInCategory.OST_PlumbingEquipment,  # Plumbing Equipment
    BuiltInCategory.OST_PlumbingFixtures,  # Plumbing Fixtures
    BuiltInCategory.OST_SecurityDevices,  # Security Devices
    BuiltInCategory.OST_SpecialityEquipment,  # Specialty Equipment
    BuiltInCategory.OST_Sprinklers,  # Sprinklers
    BuiltInCategory.OST_TelephoneDevices,  # Telephone Devices
    BuiltInCategory.OST_Wire,  # Wires
    BuiltInCategory.OST_ZoneEquipment,  # Zone Equipment
]


def get_category_by_name(doc, name):
    categories = doc.Settings.Categories
    for category in categories:
        if category.Name == name:
            return category


def get_categories(doc):
    categories = []
    for name in category_names:
        category = get_category_by_name(doc, name)
        if category:
            categories.append(category)
    return categories
