import os
import shutil
import random
from tqdm import tqdm

# Paths
source_dir = r"ML model\data\dataset"
output_dir = r"ML model\data\dataset_split"
train_ratio = 0.8

# Create target dirs
for split in ["train", "val"]:
    for label in os.listdir(source_dir):
        os.makedirs(os.path.join(output_dir, split, label), exist_ok=True)

# For each class folder
for label in os.listdir(source_dir):
    label_path = os.path.join(source_dir, label)
    if not os.path.isdir(label_path):
        continue

    files = [f for f in os.listdir(label_path) if f.endswith(".png")]
    random.shuffle(files)

    split_idx = int(len(files) * train_ratio)
    train_files = files[:split_idx]
    val_files = files[split_idx:]

    print(
        f"\n📂 Splitting {label} - Total: {len(files)} → Train: {len(train_files)}, Val: {len(val_files)}"
    )

    # Copy files
    for f in tqdm(train_files, desc=f"Copying train/{label}"):
        src = os.path.join(label_path, f)
        dst = os.path.join(output_dir, "train", label, f)
        shutil.copyfile(src, dst)

    for f in tqdm(val_files, desc=f"Copying val/{label}"):
        src = os.path.join(label_path, f)
        dst = os.path.join(output_dir, "val", label, f)
        shutil.copyfile(src, dst)

print("\n✅ Dataset split completed!")
