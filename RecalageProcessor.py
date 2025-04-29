import json
import os
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsRectangle,
    QgsFields,
    QgsField
)
from PyQt5.QtCore import QVariant

class RecalageProcessor:
    def __init__(self, json_path):
        self.json_path = json_path
        self.data = self.load_json()
        self.grid_id = self.data.get("grid_id", "unknown_grid")
        self.extent = self.get_extent()
        self.layers_to_check = self.data.get("layers", [])
        self.crs = self.data.get("crs", "")

    def load_json(self):
        with open(self.json_path, 'r') as file:
            return json.load(file)

    def get_extent(self):
        ext = self.data.get("extent", {})
        return QgsRectangle(ext["xmin"], ext["ymin"], ext["xmax"], ext["ymax"])

    def layer_in_extent(self, layer_name):
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name and layer.geometryType() == 1:  # 1 = polyline
                if layer.extent().intersects(self.extent):
                    return layer
        return None

    def extract_features(self, source_layer):
        features_to_add = []
        for feat in source_layer.getFeatures():
            if feat.geometry().intersects(self.extent):
                new_feat = QgsFeature()
                new_feat.setGeometry(feat.geometry())
                attrs = feat.attributes() + [self.grid_id]  # <-- Add grid_id as hexcode
                new_feat.setAttributes(attrs)
                features_to_add.append(new_feat)
        return features_to_add

class BatchRecalageProcessor:
    def __init__(self, json_folder, output_folder):
        self.json_folder = json_folder
        self.output_folder = output_folder
        self.merged_layer = None

    def create_empty_layer(self, crs_authid, fields):
        layer = QgsVectorLayer(f"LineString?crs={crs_authid}", "Merged_Recalage", "memory")
        pr = layer.dataProvider()
        pr.addAttributes(fields)
        layer.updateFields()
        return layer

    def run(self):
        json_files = [f for f in os.listdir(self.json_folder) if f.endswith('.json')]
        
        if not json_files:
            print("No JSON files found in the folder.")
            return

        print(f"Found {len(json_files)} JSON files to process.")

        for idx, json_file in enumerate(json_files):
            json_path = os.path.join(self.json_folder, json_file)
            print(f"\nProcessing: {json_file}")
            processor = RecalageProcessor(json_path)

            for layer_name in processor.layers_to_check:
                layer = processor.layer_in_extent(layer_name)
                if layer:
                    print(f"[{processor.grid_id}] Layer '{layer_name}' is within extent.")

                    if self.merged_layer is None:
                        fields = layer.fields()
                        fields.append(QgsField("hexcode", QVariant.String))  # Add "hexcode" field
                        self.merged_layer = self.create_empty_layer(layer.crs().authid(), fields)

                    features = processor.extract_features(layer)
                    self.merged_layer.dataProvider().addFeatures(features)
                    break  # Only take the first matching layer

        if self.merged_layer:
            self.save_merged_layer()
       

    def save_merged_layer(self):
        os.makedirs(self.output_folder, exist_ok=True)
        output_path = os.path.join(self.output_folder, "Recalage.shp")

        error = QgsVectorFileWriter.writeAsVectorFormat(self.merged_layer, output_path, "UTF-8", self.merged_layer.crs(), "ESRI Shapefile")

        if error == QgsVectorFileWriter.NoError:
            print(f"Merged layer successfully saved to {output_path}")
        else:
            print(f"Error saving merged layer to {output_path}")

# ========================

# Set the folders
#json_folder = r"C:\Users\essayeh.omar_amaris\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\Mismatch_Identifier_Plugin\Classified_images\cartography_error"
#output_folder = r"C:\Users\essayeh.omar_amaris\Desktop\recalage"

# Run batch processor
#batch_processor = BatchRecalageProcessor(json_folder, output_folder)
#batch_processor.run()
