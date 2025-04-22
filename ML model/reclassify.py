import os
import csv
import numpy as np
from PIL import Image
from collections import defaultdict
from scipy.spatial import KDTree
from tqdm import tqdm  # ✅ NEW: for progress bar

# Color definitions
GREEN = (24, 232, 69)
RED = (255, 0, 4)
BLUE = (4, 0, 254)
ORANGE = (254, 165, 0)
WHITE = (255, 255, 255)

# Paths
base_path = r"C:\Users\essayeh.omar_amaris\Desktop\ML model\data\old_classification"
folders = ["cartography_error", "no_cartography_error", "please_check", "random"]
output_csv = os.path.join(base_path, "classification_comparison.csv")

# Distance helpers
def points_distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))

def get_pixel_locations(image_array, color):
    return np.argwhere(np.all(image_array == color, axis=-1))

# Classification logic
def classify_image(img_array):
    if np.all(img_array == WHITE):
        return "random"

    green_pts = get_pixel_locations(img_array, GREEN)
    red_pts = get_pixel_locations(img_array, RED)
    blue_pts = get_pixel_locations(img_array, BLUE)
    orange_pts = get_pixel_locations(img_array, ORANGE)

    # Rule: If no cables, ignore
    if len(green_pts) == 0 and len(red_pts) == 0:
        return "random"

    # Check building distance
    if len(blue_pts) > 0 and len(orange_pts) > 0:
        blue_tree = KDTree(blue_pts)
        distances, _ = blue_tree.query(orange_pts)
        min_dist = np.min(distances)
    else:
        min_dist = None

    # Check cable overlap (within 3px)
    cable_overlap = False
    if len(red_pts) > 0 and len(green_pts) > 0:
        green_tree = KDTree(green_pts)
        dists, _ = green_tree.query(red_pts, distance_upper_bound=3)
        cable_overlap = np.any(np.isfinite(dists))

    # Check building overlap (within 3px)
    building_overlap = False
    if len(orange_pts) > 0 and len(blue_pts) > 0:
        blue_tree = KDTree(blue_pts)
        dists, _ = blue_tree.query(orange_pts, distance_upper_bound=3)
        building_overlap = np.any(np.isfinite(dists))

    # Apply rules
    if min_dist is not None and min_dist > 0.5 and not building_overlap:
        return "cartography_error"

    if cable_overlap:
        if building_overlap:
            return "no_cartography_error"
        else:
            return "cartography_error"
    else:
        if min_dist is not None and 0 < min_dist <= 0.5:
            return "please_check"
        else:
            return "random"

# Start processing
results = []

print("🚀 Starting reclassification of images...\n")

for folder in folders:
    folder_path = os.path.join(base_path, folder)
    files = [f for f in os.listdir(folder_path) if f.endswith(".png")]

    print(f"📂 Processing folder: {folder} ({len(files)} images)")
    
    for filename in tqdm(files, desc=f"🔄 Classifying", unit="image"):
        full_path = os.path.join(folder_path, filename)
        img = Image.open(full_path).convert("RGB")
        img_array = np.array(img)

        new_label = classify_image(img_array)
        results.append([filename, folder, new_label, folder == new_label])

print("\n✅ Image classification complete.")

# Write results to CSV
with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["image_name", "old_label", "new_label", "match"])
    writer.writerows(results)

print(f"📁 Results saved to: {output_csv}")
