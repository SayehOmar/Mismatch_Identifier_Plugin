import os
import json
from PyQt5.QtCore import QSize
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

        # Load other vector layers (optional: customize this as needed)
        self.other_layers = [layer for layer in QgsProject.instance().mapLayers().values()
                             if isinstance(layer, QgsVectorLayer)]
        
        # Make sure the grid layer is part of the rendering layers
        if self.grid_layer not in self.other_layers:
            self.other_layers.append(self.grid_layer)

        # Initialize map settings
        self.map_settings = QgsMapSettings()
        self.map_settings.setLayers(self.other_layers)
        self.map_settings.setBackgroundColor(QColor(255, 255, 255))

        # Set output image size
        self.image_width = 2000
        self.image_height = 2000
        self.map_settings.setOutputSize(QSize(self.image_width, self.image_height))

    def capture_grid_cells(self):
        if not self.grid_layer:
            print("⚠️ Cannot proceed without a valid grid layer.")
            return

        for feature in self.grid_layer.getFeatures():
            geom = feature.geometry()
            extent = geom.boundingBox()

            self.map_settings.setExtent(extent)

            image = QImage(self.image_width, self.image_height, QImage.Format_RGB888)
            image.fill(QColor(255, 255, 255))

            painter = QPainter(image)

            map_renderer_job = QgsMapRendererParallelJob(self.map_settings)
            map_renderer_job.start()
            map_renderer_job.waitForFinished()

            rendered_image = map_renderer_job.renderedImage()
            painter.drawImage(0, 0, rendered_image)
            painter.end()

            image_path = os.path.join(self.output_folder, f"cell_{feature.id()}.png")
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

            print(f"✅ Captured image for Cell {feature.id()} at {image_path}")
            print(f"📝 Saved metadata for Cell {feature.id()} at {metadata_path}")

        print("🎉 All grid cells captured successfully!")

