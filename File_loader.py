import os
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QFileDialog
from qgis.core import QgsProject, QgsVectorLayer

class FileLoader(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(FileLoader, self).__init__(parent)
        uic.loadUi('Mismatch_Identifier_Plugin_dialog_base.ui', self)  # Load your UI file

        
    def open_file_dialog(self, line_edit):
        """Open a file dialog to select a folder and set it in the specified QLineEdit."""
        options = QtWidgets.QFileDialog.Options()
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            "",
            options=options,
        )
        if folder_path:
            print(f"Selected folder path: {folder_path}") 
            widget_text=folder_path
            line_edit.setText(widget_text)

    def load_layers(self):
        """Loads shapefiles from the folders and applies the styles from the style folder."""
        folder1_path = self.Sauvegarde_Avant_AI.text().strip()
        folder2_path = self.Sauvegarde_Apres_AI.text().strip()
        style_folder_path = self.Styles.text().strip()

        print(f"Folder 1 Path: {repr(folder1_path)}")
        print(f"Folder 2 Path: {repr(folder2_path)}")
        print(f"Style Folder Path: {repr(style_folder_path)}")

        self.load_shapefiles(folder1_path, style_folder_path)
        self.load_shapefiles(folder2_path, style_folder_path)

    def load_shapefiles(self, folder_path, style_folder_path):
        """Loads shapefiles from a folder and applies the styles from the style folder."""
        
        
        folder_path = os.path.normpath(folder_path)
        
        if not folder_path:
            return  # Skip if folder path is empty
         
        print(f"Final folder path before checking existence: {repr(folder_path)}")
        
        print(f"Selected folder path after replacement: {folder_path}") 
        if not os.path.exists(folder_path):
            QtWidgets.QMessageBox.warning(self, "Error", f"Folder not found: {folder_path}")
            return

        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".shp"):
                layer_path = os.path.join(folder_path, filename)
                layer = QgsVectorLayer(layer_path, filename, 'ogr')

                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    print(f"Loaded layer: {filename}")

                    # Apply the style if provided
                    if style_folder_path:
                        self.apply_style_from_folder(layer, style_folder_path)
                else:
                    QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load layer: {filename}")

    def apply_style_from_folder(self, layer, style_folder_path):
        """Applies a style from the style folder to the layer, based on matching layer name."""
        layer_name = layer.name().lower()  # Get layer name in lowercase
        for style_filename in os.listdir(style_folder_path):
            style_filepath = os.path.join(style_folder_path, style_filename)
            if style_filename.lower().startswith(layer_name) and style_filename.lower().endswith((".qml", ".sld")):
                if style_filename.lower().endswith(".qml"):
                    layer.loadNamedStyle(style_filepath)
                    print(f"Applied style from {style_filepath} to {layer.name()}")
                elif style_filename.lower().endswith(".sld"):
                    layer.loadSldStyle(style_filepath)
                    print(f"Applied style from {style_filepath} to {layer.name()}")
                return # apply only one style per layer.