# qgis_setup.py
import sys
import os

# Add QGIS Python paths
qgis_path = r"C:\Program Files\QGIS 3.34.15"
qgis_python_path = os.path.join(qgis_path, "apps", "qgis-ltr", "python")
user_profile_path = os.path.join(os.environ['APPDATA'], "QGIS", "QGIS3", "profiles", "default", "python")

# Append all necessary paths
paths_to_add = [
    qgis_python_path,
    user_profile_path,
    os.path.join(user_profile_path, "plugins"),
    os.path.join(qgis_path, "apps", "qgis-ltr", "python", "plugins"),
    os.path.join(qgis_path, "apps", "grass", "grass84", "etc", "python")
]

for path in paths_to_add:
    if os.path.exists(path) and path not in sys.path:
        sys.path.append(path)

# Set QGIS prefix path
os.environ['QGIS_PREFIX_PATH'] = os.path.join(qgis_path, "apps", "qgis-ltr")

# Now try importing QGIS
try:
    from qgis.core import QgsApplication
    # Initialize QGIS application
    qgs = QgsApplication([], False)
    qgs.initQgis()
    print("QGIS environment successfully initialized!")
    
    # Now you can import other QGIS modules
    from qgis.core import QgsVectorLayer, QgsProject
    print("Additional QGIS modules imported successfully!")
    
except ImportError as e:
    print(f"Failed to import QGIS: {e}")
    print("Current sys.path:")
    for p in sys.path:
        print(f"  {p}")