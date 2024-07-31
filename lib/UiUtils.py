import clr

clr.AddReferenceByPartialName("System")

from System import Windows


class SelectFromList(Windows.Window):
    def __init__(self, items):
        self.items = items
        self.InitializeComponent()

    def InitializeComponent(self):
        self.Title = "Select item"
        self.Topmost = True
        self.Width = 300
        self.Height = 400
        self.WindowStartupLocation = Windows.WindowStartupLocation.CenterScreen
        self.listBox = Windows.Controls.ListBox()
        self.listBox.SelectionMode = Windows.Controls.SelectionMode.Single
        self.listBox.ItemsSource = self.items
        self.listBox.SelectionChanged += self.listBox_SelectionChanged
        self.Content = self.listBox
        self.Topmost = True

    def listBox_SelectionChanged(self, sender, e):
        self.Close()

    def show(self):
        self.ShowDialog()
        return self.listBox.SelectedItem


class Alert(Windows.Window):
    def __init__(self, message, title="Alert", flow_direction="ltr", ok_btn_text="OK"):
        self.message = message
        self.title = title
        self.flow_direction = (
            Windows.FlowDirection.RightToLeft
            if flow_direction == "rtl"
            else Windows.FlowDirection.LeftToRight
        )
        self.ok_btn_text = ok_btn_text
        self.InitializeComponent()

    def InitializeComponent(self):
        self.Title = self.title
        self.Topmost = True
        self.Width = 300
        self.Height = 200
        self.WindowStartupLocation = Windows.WindowStartupLocation.CenterScreen

        self.textBlock = Windows.Controls.TextBlock()
        self.textBlock.Text = self.message
        self.textBlock.TextWrapping = Windows.TextWrapping.Wrap
        self.textBlock.Margin = Windows.Thickness(10)
        self.textBlock.FlowDirection = self.flow_direction

        self.button = Windows.Controls.Button()
        self.button.Content = self.ok_btn_text
        self.button.Margin = Windows.Thickness(10)
        self.button.Click += self.button_Click

        self.grid = Windows.Controls.Grid()
        self.row1 = Windows.Controls.RowDefinition()
        self.row2 = Windows.Controls.RowDefinition()
        self.row2.Height = Windows.GridLength(50)
        self.grid.RowDefinitions.Add(self.row1)
        self.grid.RowDefinitions.Add(self.row2)
        self.grid.Children.Add(self.textBlock)
        self.grid.Children.Add(self.button)
        Windows.Controls.Grid.SetRow(self.textBlock, 0)
        Windows.Controls.Grid.SetRow(self.button, 1)

        self.Content = self.grid
        self.Topmost = True

    def button_Click(self, sender, e):
        self.Close()

    def show(self):
        self.ShowDialog()


def get_button_style1():
    button_style = Windows.Style()
    button_style.Setters.Add(
        Windows.Setter(
            Windows.Controls.Button.PaddingProperty, Windows.Thickness(8, 4, 8, 4)
        )
    )
    button_style.Setters.Add(
        Windows.Setter(
            Windows.Controls.Button.BorderBrushProperty,
            Windows.Media.Brushes.Transparent,
        )
    )
    button_style.Setters.Add(
        Windows.Setter(
            Windows.Controls.Button.CursorProperty,
            Windows.Input.Cursors.Hand,
        )
    )

    return button_style
