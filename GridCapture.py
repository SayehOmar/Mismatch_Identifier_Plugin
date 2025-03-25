import os
import json  # Import the json module
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QImage, QPainter, QColor
from qgis.core import *
from qgis.utils import iface

class GridCapture:
    def __init__(self, grid_layer_path, output_folder):
        self.grid_layer_path = grid_layer_path
        self.output_folder = output_folder

        # Ensure the output folder exists
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        print(f"Grid Layer Path: {self.grid_layer_path}")
        # Load the grid layer
        self.grid_layer = QgsVectorLayer(self.grid_layer_path, "grid", "ogr")

        if not self.grid_layer.isValid():
            print("Failed to load the grid layer! Exiting.")
            return

        # Load other layers (you can modify to include any layers you want)
        self.other_layers = [layer for layer in QgsProject.instance().mapLayers().values() if isinstance(layer, QgsVectorLayer)]
        self.other_layers.append(self.grid_layer)  # Add the grid layer as well

        # Initialize map settings
        self.map_settings = QgsMapSettings()
        self.map_settings.setLayers(self.other_layers)  # Set all layers to render
        self.map_settings.setBackgroundColor(QColor(255, 255, 255))  # White background

        # Set image size for output
        self.image_width = 2000  # Set width
        self.image_height = 2000  # Set height
        self.map_settings.setOutputSize(QSize(self.image_width, self.image_height))

    def capture_grid_cells(self):
        # Iterate through each grid cell
        for feature in self.grid_layer.getFeatures():
            geom = feature.geometry()
            extent = geom.boundingBox()  # Get the bounding box for the cell
            print(f"Layer CRS: {self.grid_layer.crs().authid()}")

            # Set extent (zoom) for the map renderer to the current grid cell
            self.map_settings.setExtent(extent)

            # Set up a QImage to store the rendered image
            image = QImage(self.image_width, self.image_height, QImage.Format_RGB888)
            image.fill(QColor(255, 255, 255))  # Set background color to white

            # Set up QPainter to draw the image
            painter = QPainter(image)

            # Set up map renderer job (renders all layers)
            map_renderer_job = QgsMapRendererParallelJob(self.map_settings)
            map_renderer_job.start()
            map_renderer_job.waitForFinished()

            # Get the rendered image
            rendered_image = map_renderer_job.renderedImage()

            # Draw the rendered image onto the painter
            painter.drawImage(0, 0, rendered_image)

            # End the painting process
            painter.end()

            # Save the rendered image as a PNG file
            image_path = os.path.join(self.output_folder, f"cell_{feature.id()}.png")
            image.save(image_path)  # Save the image

            # Create metadata dictionary
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

            # Save metadata to a JSON file
            metadata_path = os.path.join(self.output_folder, f"cell_{feature.id()}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=4)  # Save with indentation for readability

            print(f"Captured image for Cell {feature.id()} at {image_path}")
            print(f"Saved metadata for Cell {feature.id()} at {metadata_path}")

        print("✅ All grid cells captured successfully!")