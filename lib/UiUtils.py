import clr

clr.AddReferenceByPartialName("System")

from System import Windows


class SelectFromList(Windows.Window):
    def __init__(self, items):
        self.items = items
        self.InitializeComponent()

    def InitializeComponent(self):
        self.Title = "Select item"
        self.Width = 300
        self.Height = 400
        self.WindowStartupLocation = Windows.WindowStartupLocation.CenterScreen
        self.listBox = Windows.Controls.ListBox()
        self.listBox.SelectionMode = Windows.Controls.SelectionMode.Single
        self.listBox.ItemsSource = self.items
        self.listBox.SelectionChanged += self.listBox_SelectionChanged
        self.Content = self.listBox

    def listBox_SelectionChanged(self, sender, e):
        self.Close()

    def show(self):
        self.ShowDialog()
        return self.listBox.SelectedItem
