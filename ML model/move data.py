import os
import shutil
import pandas as pd
from tqdm import tqdm

# Paths
base_dir = r"C:\Users\essayeh.omar_amaris\Desktop\ML model\data"
csv_path = os.path.join(base_dir, "classification_comparison.csv")
source_base = os.path.join(base_dir, "old_classification")
dest_base = os.path.join(base_dir, "dataset")

# Load CSV
df = pd.read_csv(csv_path)

# Create destination folders
new_labels = df['new_label'].unique()
for label in new_labels:
    os.makedirs(os.path.join(dest_base, label), exist_ok=True)

# Move files with a progress bar
print("Organizing files into new folders based on new_label...")
for _, row in tqdm(df.iterrows(), total=len(df)):
    src = os.path.join(source_base, row['old_label'], row['image_name'])
    dst = os.path.join(dest_base, row['new_label'], row['image_name'])

    if os.path.exists(src):
        shutil.move(src, dst)
    else:
        print(f"❌ Missing: {src}")
