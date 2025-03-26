import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np
import math

class GridGenerator:
    def __init__(self, roi_path, grid_size=10, output_path="Grid/grid.shp"):
        """
        Initialize the GridGenerator with the given parameters.

        Parameters:
        - roi_path (str): Path to the ROI shapefile.
        - grid_size (int): The size of each grid cell in meters. Default is 20.
        - output_path (str): The path to save the generated grid shapefile.
        """
        self.roi_path = roi_path
        self.grid_size = grid_size
        self.output_path = output_path
        self.roi = self.load_roi()

    def load_roi(self):
        """Load the ROI shapefile into a GeoDataFrame."""
        return gpd.read_file(self.roi_path)

    def round_up(self, value):
        """Round up to the nearest multiple of grid_size."""
        return math.ceil(value / self.grid_size) * self.grid_size

    def round_down(self, value):
        """Round down to the nearest multiple of grid_size."""
        return math.floor(value / self.grid_size) * self.grid_size

    def adjust_bounding_box(self, xmin, ymin, xmax, ymax):
        """Adjust the bounding box to be divisible by grid_size."""
        xmin = self.round_down(xmin)
        ymin = self.round_down(ymin)
        xmax = self.round_up(xmax)
        ymax = self.round_up(ymax)
        return xmin, ymin, xmax, ymax

    def generate_grid(self):
        """Generate the grid cells within the ROI bounding box."""
        xmin, ymin, xmax, ymax = self.roi.total_bounds  # Get min/max X and Y
        xmin, ymin, xmax, ymax = self.adjust_bounding_box(xmin, ymin, xmax, ymax)

        grid_cells = []
        for x in np.arange(xmin, xmax, self.grid_size):
            for y in np.arange(ymin, ymax, self.grid_size):
                grid_cells.append(Polygon([(x, y), (x + self.grid_size, y),
                                           (x + self.grid_size, y + self.grid_size), (x, y + self.grid_size)]))

        # Create GeoDataFrame for the grid
        grid = gpd.GeoDataFrame(geometry=grid_cells, crs=self.roi.crs)
        return grid

    def save_grid(self):
        """Generate and save the grid to a shapefile."""
        grid = self.generate_grid()
        grid.to_file(self.output_path)
        print(f"Grid generated and saved at: {self.output_path}")


