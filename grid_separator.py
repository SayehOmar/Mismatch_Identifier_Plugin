import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np
import math

# Load the ROI shapefile
roi_path = "ROI/ROI.shp"
roi = gpd.read_file(roi_path)

# Get the bounding box of the ROI
xmin, ymin, xmax, ymax = roi.total_bounds  # Get min/max X and Y

# Ensure the bounding box is divisible by 20m
grid_size = 10  # 20m x 20m

def round_up(value, grid_size):
    """Round up to the nearest multiple of grid_size."""
    return math.ceil(value / grid_size) * grid_size

def round_down(value, grid_size):
    """Round down to the nearest multiple of grid_size."""
    return math.floor(value / grid_size) * grid_size

# Adjust bounding box to be divisible by 20m
xmin = round_down(xmin, grid_size)
ymin = round_down(ymin, grid_size)
xmax = round_up(xmax, grid_size)
ymax = round_up(ymax, grid_size)

# Generate grid cells
grid_cells = []
for x in np.arange(xmin, xmax, grid_size):
    for y in np.arange(ymin, ymax, grid_size):
        grid_cells.append(Polygon([(x, y), (x + grid_size, y), 
                                   (x + grid_size, y + grid_size), (x, y + grid_size)]))

# Create GeoDataFrame for the grid
grid = gpd.GeoDataFrame(geometry=grid_cells, crs=roi.crs)

# Save the grid to a new shapefile
grid_output_path = "Grid\grid.shp"
grid.to_file(grid_output_path)

print(f"Grid generated and saved at: {grid_output_path}")
