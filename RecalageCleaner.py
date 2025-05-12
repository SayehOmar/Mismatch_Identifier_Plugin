from qgis.core import QgsVectorLayer, QgsFeature, QgsVectorFileWriter, QgsProject
import os

class RecalageCleaner:
    def __init__(self, output_folder):
        self.shapefile_path = os.path.join(output_folder, "recalage.shp")

    def run(self):
        # Load the shapefile from disk
        layer = QgsVectorLayer(self.shapefile_path, "recalage_cleaned", "ogr")
        if not layer.isValid():
            raise Exception(f"Failed to load shapefile: {self.shapefile_path}")

        # Filter out features with CLASSE == 'A'
        cleaned_features = [f for f in layer.getFeatures() if f["CLASSE"] != 'A']

        # Save the filtered features back to the same file (overwrite)
        writer = QgsVectorFileWriter(
            self.shapefile_path,
            'UTF-8',
            layer.fields(),
            layer.wkbType(),
            layer.sourceCrs(),
            'ESRI Shapefile'
        )

        for feature in cleaned_features:
            writer.addFeature(feature)
        del writer  # Ensure file is closed

        print(f"✅ Cleaned shapefile saved to: {self.shapefile_path}")
