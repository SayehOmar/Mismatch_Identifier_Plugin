from qgis.core import *
from qgis.utils import iface
import os

# Load the grid layer (Update path accordingly)
grid_layer = QgsVectorLayer("C:/path/to/grid.shp", "grid", "ogr")

# Define output folder
output_folder = "C:/path/to/output_images/"

# Ensure output folder exists
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Loop through each grid cell
for feature in grid_layer.getFeatures():
    geom = feature.geometry()
    extent = geom.boundingBox()  # Get cell extent

    # Set canvas extent to the grid cell
    iface.mapCanvas().setExtent(extent)

    # Force refresh
    iface.mapCanvas().refresh()

    # Save image
    image_path = os.path.join(output_folder, f"cell_{feature.id()}.png")
    iface.mapCanvas().saveAsImage(image_path)

    print(f"Saved: {image_path}")

print("✅ All grid cells captured successfully!")
