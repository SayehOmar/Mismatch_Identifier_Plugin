import os
import json
from PyQt5.QtCore import QSize,QCoreApplication
from PyQt5.QtGui import QImage, QPainter, QColor
from qgis.core import *
from qgis.utils import iface

class GridCapture:
    def __init__(self, output_folder):
        self.output_folder = output_folder

        # Ensure the output folder exists
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        # Fetch the already-loaded grid layer by name
        self.grid_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Filtered_Grid" and isinstance(layer, QgsVectorLayer):
                self.grid_layer = layer
                break

        if not self.grid_layer:
            print("❌ Grid layer 'Filtered_Grid' not found in the current QGIS project.")
            return

        print(f"✅ Found grid layer: {self.grid_layer.name()}")

        # Load other vector layers (excluding the grid layer)
        self.other_layers = [layer for layer in QgsProject.instance().mapLayers().values()
                             if isinstance(layer, QgsVectorLayer) and layer.name() != "Filtered_Grid"]
        
        print(f"✅ Found {len(self.other_layers)} other layers to render")

        # Initialize map settings
        self.map_settings = QgsMapSettings()
        self.map_settings.setLayers(self.other_layers)  # Don't include grid in rendered layers
        self.map_settings.setBackgroundColor(QColor(255, 255, 255))

        # Set output image size - reduce for faster processing
        self.image_width = 1200  # Reduced from 2000
        self.image_height = 1200  # Reduced from 2000
        self.map_settings.setOutputSize(QSize(self.image_width, self.image_height))
        
        # Set renderer flags for better performance
        self.map_settings.setFlag(QgsMapSettings.Flag.Antialiasing, False)
        self.map_settings.setFlag(QgsMapSettings.Flag.UseAdvancedEffects, False)
        
        print("✅ Map settings initialized with optimized parameters")

    def capture_grid_cells(self):
        if not self.grid_layer:
            print("⚠️ Cannot proceed without a valid grid layer.")
            return
            
        total_features = self.grid_layer.featureCount()
        print(f"🔍 Found {total_features} grid cells to process")
            
        # Process features in batches to avoid slow GUI updates
        batch_size = 10
        feature_counter = 0
        
        for feature in self.grid_layer.getFeatures():
            feature_counter += 1
            geom = feature.geometry()
            extent = geom.boundingBox()
            
            # Skip processing if output file already exists (for resuming interrupted processes)
            image_path = os.path.join(self.output_folder, f"cell_{feature.id()}.png")
            if os.path.exists(image_path):
                print(f"📋 Cell {feature.id()} already processed, skipping ({feature_counter}/{total_features})")
                continue

            self.map_settings.setExtent(extent)

            # Create image and painter
            image = QImage(self.image_width, self.image_height, QImage.Format_RGB888)
            image.fill(QColor(255, 255, 255))
            painter = QPainter(image)

            # Use parallel rendering for better performance
            map_renderer_job = QgsMapRendererParallelJob(self.map_settings)
            map_renderer_job.start()
            map_renderer_job.waitForFinished()

            rendered_image = map_renderer_job.renderedImage()
            painter.drawImage(0, 0, rendered_image)
            painter.end()

            # Save image and metadata
            image.save(image_path)

            metadata = {
                "grid_id": feature.id(),
                "extent": {
                    "xmin": extent.xMinimum(),
                    "ymin": extent.yMinimum(),
                    "xmax": extent.xMaximum(),
                    "ymax": extent.yMaximum(),
                },
                "crs": self.grid_layer.crs().authid(),
                "layers": [layer.name() for layer in self.other_layers],
            }

            metadata_path = os.path.join(self.output_folder, f"cell_{feature.id()}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=4)

            print(f"✅ Captured image for Cell {feature.id()} ({feature_counter}/{total_features})")
            
            
            if feature_counter % batch_size == 0:
                QCoreApplication.processEvents()

        print("🎉 All grid cells captured successfully!")