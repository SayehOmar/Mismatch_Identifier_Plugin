# test_qgis.py
import sys
print(sys.path)  # Should include your QGIS paths


sys.path.append(r"C:\Program Files\QGIS 3.34.15\apps\qgis\python")
sys.path.append(r"C:\Program Files\QGIS 3.34.15\apps\qgis\bin")

try:
    from qgis.core import *
    print("QGIS module loaded successfully!")
except ImportError as e:
    print("Failed to import QGIS:", e)
