import os
from qgis.core import QgsProject

output_folder = "QML_Styles"  # Replace with your desired output path

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

project = QgsProject.instance()
for layer in project.mapLayers().values():
    if layer.isValid() and isinstance(layer, QgsVectorLayer):  # Or QgsRasterLayer, etc.
        sld_path = os.path.join(output_folder, f"{layer.name()}.sld")
        layer.saveSldStyle(sld_path)
        print(f"Saved SLD style for {layer.name()} to {sld_path}")

print("✅ All SLD styles exported successfully!")