import json
import os
import time
from datetime import datetime, timedelta
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
        
        # Time tracking variables
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.processed_files = 0
        self.total_files = 0
        self.processing_times = []
        self.update_interval = 300  # 5 minutes in seconds

    def create_empty_layer(self, crs_authid, fields):
        layer = QgsVectorLayer(f"LineString?crs={crs_authid}", "Merged_Recalage", "memory")
        pr = layer.dataProvider()
        pr.addAttributes(fields)
        layer.updateFields()
        return layer

    def write_time_estimate(self):
        """Write time estimation to a file"""
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        
        # Only calculate remaining time if we've processed at least one file
        if self.processed_files > 0:
            avg_time_per_file = sum(self.processing_times) / len(self.processing_times)
            remaining_files = self.total_files - self.processed_files
            estimated_remaining_time = avg_time_per_file * remaining_files
            
            # Format as readable time
            remaining_time_str = str(timedelta(seconds=int(estimated_remaining_time)))
            
            # Create content for the file
            content = (
                f"Progress update at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Files processed: {self.processed_files} of {self.total_files}\n"
                f"Files remaining: {remaining_files}\n"
                f"Average processing time per file: {avg_time_per_file:.2f} seconds\n"
                f"Estimated remaining time: {remaining_time_str}\n"
                f"Elapsed time: {str(timedelta(seconds=int(elapsed_time)))}\n"
            )
            
            # Write to file
            with open(os.path.join(self.output_folder, "remaining_time.txt"), "w") as f:
                f.write(content)
                
            print("Updated time estimation file")
            
        self.last_update_time = current_time

    def check_update_time(self):
        """Check if it's time to update the time estimation file"""
        if (time.time() - self.last_update_time) >= self.update_interval:
            self.write_time_estimate()

    def run(self):
        json_files = [f for f in os.listdir(self.json_folder) if f.endswith('.json')]
        
        if not json_files:
            print("No JSON files found in the folder.")
            return

        self.total_files = len(json_files)
        print(f"Found {self.total_files} JSON files to process.")
        
        # Ensure output folder exists
        os.makedirs(self.output_folder, exist_ok=True)

        for idx, json_file in enumerate(json_files):
            file_start_time = time.time()
            json_path = os.path.join(self.json_folder, json_file)
            print(f"\nProcessing: {json_file} ({idx+1}/{self.total_files})")
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
            
            # Track processing time for this file
            file_processing_time = time.time() - file_start_time
            self.processing_times.append(file_processing_time)
            self.processed_files += 1
            
            # Check if we need to update the time estimation file
            self.check_update_time()

        if self.merged_layer:
            self.save_merged_layer()
        
        # Final update to the time estimation file
        with open(os.path.join(self.output_folder, "remaining_time.txt"), "w") as f:
            f.write(f"Process completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total files processed: {self.processed_files}\n")
            f.write(f"Total processing time: {str(timedelta(seconds=int(time.time() - self.start_time)))}\n")

    def save_merged_layer(self):
        os.makedirs(self.output_folder, exist_ok=True)
        output_path = os.path.join(self.output_folder, "Recalage.shp")

        error = QgsVectorFileWriter.writeAsVectorFormat(self.merged_layer, output_path, "UTF-8", self.merged_layer.crs(), "ESRI Shapefile")

        if error == QgsVectorFileWriter.NoError:
            print(f"Merged layer successfully saved to {output_path}")
        else:
            print(f"Error saving merged layer to {output_path}")