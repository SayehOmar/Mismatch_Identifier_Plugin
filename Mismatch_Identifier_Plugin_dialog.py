import os
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from .GridCapture import GridCapture
from .File_loader import FileLoader
from .grid_filter import GridFilter


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "Mismatch_Identifier_Plugin_dialog_base.ui")
)

class Mismatch_Identifier_PluginDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(Mismatch_Identifier_PluginDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # Connect the Start Process button
        self.Start_Process.clicked.connect(self.on_start_process_clicked)

        # Create a FileLoader instance
        self.file_loader = FileLoader(self)

        # Connect the browse buttons from FileLoader to the current dialog
        self.Sauvegarde_Avant_AI_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Sauvegarde_Avant_AI, 'folder1_path')
        )
        self.Sauvegarde_Apres_AI_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Sauvegarde_Apres_AI, 'folder2_path')
        )
        self.Styles_Button.clicked.connect(
            lambda: self.file_loader.open_file_dialog(self.Styles, 'style_folder_path')
        )
        # Connect the Generate Grid button to the function that will create the grid
        self.Start_Process.clicked.connect(self.on_generate_grid)
        # Connect load button to load layers function
        self.StartLoading.clicked.connect(self.file_loader.load_layers)

    def on_start_process_clicked(self):
        """Placeholder method for the Start Process button."""
        # You can add the logic that should happen when the 'Start Process' button is clicked.
        pass

    def on_generate_grid(self):
        """Callback for the Generate Grid button to generate grid."""
        reference_layer_name = "Arc_itineraire_AV"  # Name of the reference layer
        try:
            # Create a GridFilter instance
            grid_filter = GridFilter(reference_layer_name)

            # Select layers within the buffer (5 meters)
            grid_filter.select_layers_within_buffer()

            # Create the ROI from the selected layers
            grid_filter.create_roi_from_bbox()

            # Apply the grid separator and save the grid
            grid_filter.apply_grid_separator()

            QtWidgets.QMessageBox.information(self, "Success", "Grid generated and saved successfully!")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

       
    