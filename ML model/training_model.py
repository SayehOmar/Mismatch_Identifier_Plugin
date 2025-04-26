import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
import os
from tqdm import tqdm
import numpy as np
from multiprocessing import freeze_support

# Define data directories (keep these outside as they are constants)
train_dir = r"ML model\data\dataset_split\train"
val_dir = r"ML model\data\dataset_split\val"
best_model_path = "best_color_model.pth"
image_size = 800
batch_size = 8
num_epochs = 30
patience = 5

# Define transformations (keep these outside as they are constants)
train_transforms = transforms.Compose(
    [
        transforms.Resize((image_size, image_size)),
        transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.05),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)

val_transforms = transforms.Compose(
    [
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


# Define the CNN model (keep this outside as it's a class definition)
class ColorFocusedCNN(nn.Module):
    def __init__(self, num_classes):
        super(ColorFocusedCNN, self).__init__()
        self.block1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        self.block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        self.block3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        self.color_attention = nn.Sequential(
            nn.Conv2d(128, 128, kernel_size=1), nn.BatchNorm2d(128), nn.Sigmoid()
        )
        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        attention = self.color_attention(x)
        x = x * attention
        x = self.gap(x)
        x = x.view(x.size(0), -1)
        x = self.dropout(x)
        x = self.fc(x)
        return x


# Function to compute color histograms (can be used for analysis)
def compute_color_histogram(batch):
    if batch.is_cuda:
        batch_np = batch.cpu().numpy()
    else:
        batch_np = batch.numpy()
    batch_np = batch_np.reshape(batch_np.shape[0], 3, -1)
    histograms = []
    for i in range(batch_np.shape[0]):
        hist = []
        for c in range(3):
            h, _ = np.histogram(batch_np[i, c, :], bins=10, range=(0, 1))
            hist.extend(h)
        histograms.append(hist)
    return np.array(histograms)


# Function to display color distribution of an image (useful for analysis)
def analyze_image_colors(image_path, transform=None):
    from PIL import Image
    import matplotlib.pyplot as plt

    image = Image.open(image_path).convert("RGB")
    if transform is None:
        transform = val_transforms
    image_tensor = transform(image)
    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.imshow(np.transpose(image_tensor.numpy(), (1, 2, 0)))
    plt.title("Original Image")
    plt.subplot(1, 2, 2)
    colors = ["red", "green", "blue"]
    for i, color in enumerate(colors):
        channel_data = image_tensor[i].numpy().flatten()
        plt.hist(channel_data, bins=50, alpha=0.6, color=color, label=color)
    plt.title("Color Distribution")
    plt.legend()
    plt.tight_layout()
    plt.show()


# Function to predict on a single image
def predict_image(image_path, model, transform):
    from PIL import Image

    image = Image.open(image_path).convert("RGB")
    image_tensor = transform(image).unsqueeze(0).to(device)
    model.eval()
    with torch.no_grad():
        output = model(image_tensor)
        _, predicted = torch.max(output, 1)
        probability = torch.nn.functional.softmax(output, dim=1)[0][
            predicted.item()
        ].item()
    return class_names[predicted.item()], probability


if __name__ == "__main__":
    freeze_support()

    # Load datasets
    train_dataset = datasets.ImageFolder(train_dir, transform=train_transforms)
    val_dataset = datasets.ImageFolder(val_dir, transform=val_transforms)

    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=2,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
    )

    # Get class names and number of classes
    class_names = train_dataset.classes
    num_classes = len(class_names)
    print(f"Valid classes detected: {class_names}")
    print(f"Number of classes: {num_classes}")
    print(f"Class mapping: {train_dataset.class_to_idx}")
    print(f"Training samples: {len(train_dataset)}")
    print(f"Validation samples: {len(val_dataset)}")

    # Initialize model and move to GPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ColorFocusedCNN(num_classes).to(device)
    print(f"Using device: {device}")

    # Set CUDA options
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        print("CUDA optimization enabled")

    # Define loss function and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=3
    )

    # Parameters for training (already defined outside)
    best_val_loss = float("inf")
    counter = 0

    # Training loop
    for epoch in range(num_epochs):
        # Training phase
        model.train()
        train_loss = 0.0
        train_correct = 0
        total_train = 0

        train_progress = tqdm(
            enumerate(train_loader),
            total=len(train_loader),
            desc=f"Epoch {epoch+1}/{num_epochs} - Training",
        )

        for i, (inputs, labels) in train_progress:
            inputs = inputs.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs.data, 1)
            total_train += labels.size(0)
            train_correct += (predicted == labels).sum().item()

            train_progress.set_postfix({"loss": f"{loss.item():.4f}"})

        train_loss = train_loss / total_train
        train_accuracy = 100 * train_correct / total_train

        # Validation phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        total_val = 0

        val_progress = tqdm(
            enumerate(val_loader),
            total=len(val_loader),
            desc=f"Epoch {epoch+1}/{num_epochs} - Validation",
        )

        with torch.no_grad():
            for i, (inputs, labels) in val_progress:
                inputs = inputs.to(device)
                labels = labels.to(device)

                outputs = model(inputs)
                loss = criterion(outputs, labels)

                val_loss += loss.item() * inputs.size(0)
                _, predicted = torch.max(outputs.data, 1)
                total_val += labels.size(0)
                val_correct += (predicted == labels).sum().item()

                val_progress.set_postfix({"loss": f"{loss.item():.4f}"})

        val_loss = val_loss / total_val
        val_accuracy = 100 * val_correct / total_val

        scheduler.step(val_loss)

        print(f"Epoch {epoch+1}/{num_epochs}")
        print(
            f"  Training Loss: {train_loss:.4f}, Training Accuracy: {train_accuracy:.2f}%"
        )
        print(
            f"  Validation Loss: {val_loss:.4f}, Validation Accuracy: {val_accuracy:.2f}%"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            counter = 0
            print(f"  Saving best model with validation loss: {val_loss:.4f}")
            torch.save(model.state_dict(), best_model_path)
        else:
            counter += 1
            print(f"  EarlyStopping counter: {counter} out of {patience}")
            if counter >= patience:
                print("Early stopping")
                break

    print("Training finished!")

    # Load the best model for evaluation or inference
    model.load_state_dict(torch.load(best_model_path))
    print(f"Loaded best model from {best_model_path}")

    # Example usage (keep these inside if you want them to run after training)
    # result, confidence = predict_image("path/to/your/image.jpg", model, val_transforms)
    # print(f"Prediction: {result}, Confidence: {confidence*100:.2f}%")
    # analyze_image_colors("path/to/your/image.jpg")
