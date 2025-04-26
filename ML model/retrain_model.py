import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
import os
from tqdm import tqdm
import json
from multiprocessing import freeze_support


# Define our ColorFocusedCNN model class to load the model
class ColorFocusedCNN(nn.Module):
    def __init__(self, num_classes):
        super(ColorFocusedCNN, self).__init__()

        # First block - smaller kernel, more color channels
        self.block1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )

        # Second block - deeper network for color features
        self.block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )

        # Third block
        self.block3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )

        # Color histogram features
        self.color_attention = nn.Sequential(
            nn.Conv2d(128, 128, kernel_size=1), nn.BatchNorm2d(128), nn.Sigmoid()
        )

        # Global pooling and classification
        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)

        # Apply color attention
        attention = self.color_attention(x)
        x = x * attention

        x = self.gap(x)
        x = x.view(x.size(0), -1)
        x = self.dropout(x)
        x = self.fc(x)
        return x


def retrain_model(base_model_path, output_model_path, num_epochs=10):
    """
    Load a pre-trained model, retrain it, and save a new model

    Args:
        base_model_path: Path to the pre-trained model
        output_model_path: Path to save the new model
        num_epochs: Number of epochs for retraining
    """
    if __name__ == "__main__":
        freeze_support()

    # Define data directories
    train_dir = r"ML model\data\dataset_split\train"
    val_dir = r"ML model\data\dataset_split\val"

    # Try to load model info if available
    try:
        with open("model_info.json", "r") as f:
            model_info = json.load(f)
            image_size = model_info.get("image_size", 224)
            print(f"Loaded image size from model info: {image_size}")
    except:
        image_size = 224
        print(f"Using default image size: {image_size}")

    # Define batch size
    batch_size = 16

    # Define transformations
    train_transforms = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ColorJitter(
                brightness=0.1, contrast=0.1, saturation=0.1, hue=0.05
            ),
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

    # Load datasets
    print("Loading datasets...")
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
    print(f"Training samples: {len(train_dataset)}")
    print(f"Validation samples: {len(val_dataset)}")

    # Initialize model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ColorFocusedCNN(num_classes).to(device)

    # Load the pre-trained model weights
    print(f"Loading pre-trained model from {base_model_path}")
    model.load_state_dict(torch.load(base_model_path, map_location=device))
    print("Model loaded successfully!")

    # Set CUDA options
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        print("CUDA optimization enabled")

    # Define loss function and optimizer
    # Use a lower learning rate for fine-tuning
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.0001, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2
    )

    # Parameters for retraining
    best_val_loss = float("inf")
    best_model_path = output_model_path

    # Print starting model performance
    print("Evaluating initial model performance...")
    model.eval()
    val_loss = 0.0
    val_correct = 0
    total_val = 0

    with torch.no_grad():
        for inputs, labels in val_loader:
            inputs = inputs.to(device)
            labels = labels.to(device)

            outputs = model(inputs)
            loss = criterion(outputs, labels)

            val_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs.data, 1)
            total_val += labels.size(0)
            val_correct += (predicted == labels).sum().item()

    initial_val_loss = val_loss / total_val
    initial_val_accuracy = 100 * val_correct / total_val
    print(f"Initial validation loss: {initial_val_loss:.4f}")
    print(f"Initial validation accuracy: {initial_val_accuracy:.2f}%")

    # Retraining loop
    print(f"Starting retraining for {num_epochs} epochs...")
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

            # Zero the parameter gradients
            optimizer.zero_grad()

            # Forward pass
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            # Backward pass and optimize
            loss.backward()
            optimizer.step()

            # Track statistics
            train_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs.data, 1)
            total_train += labels.size(0)
            train_correct += (predicted == labels).sum().item()

            # Update progress bar
            train_progress.set_postfix({"loss": f"{loss.item():.4f}"})

        # Calculate epoch statistics
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

                # Forward pass
                outputs = model(inputs)
                loss = criterion(outputs, labels)

                # Track statistics
                val_loss += loss.item() * inputs.size(0)
                _, predicted = torch.max(outputs.data, 1)
                total_val += labels.size(0)
                val_correct += (predicted == labels).sum().item()

                # Update progress bar
                val_progress.set_postfix({"loss": f"{loss.item():.4f}"})

        # Calculate epoch statistics
        val_loss = val_loss / total_val
        val_accuracy = 100 * val_correct / total_val

        # Update learning rate based on validation loss
        scheduler.step(val_loss)

        # Print learning rate
        for param_group in optimizer.param_groups:
            current_lr = param_group["lr"]
        print(f"  Current learning rate: {current_lr}")

        # Print epoch results
        print(f"Epoch {epoch+1}/{num_epochs}")
        print(
            f"  Training Loss: {train_loss:.4f}, Training Accuracy: {train_accuracy:.2f}%"
        )
        print(
            f"  Validation Loss: {val_loss:.4f}, Validation Accuracy: {val_accuracy:.2f}%"
        )

        # Check if this is the best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            print(f"  Saving best model with validation loss: {val_loss:.4f}")
            torch.save(model.state_dict(), best_model_path)

    print("Retraining finished!")

    # Final evaluation
    model.load_state_dict(torch.load(best_model_path))
    model.eval()
    val_loss = 0.0
    val_correct = 0
    total_val = 0

    with torch.no_grad():
        for inputs, labels in val_loader:
            inputs = inputs.to(device)
            labels = labels.to(device)

            outputs = model(inputs)
            loss = criterion(outputs, labels)

            val_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs.data, 1)
            total_val += labels.size(0)
            val_correct += (predicted == labels).sum().item()

    final_val_loss = val_loss / total_val
    final_val_accuracy = 100 * val_correct / total_val

    print("\nRetraining Results:")
    print(
        f"Initial validation loss: {initial_val_loss:.4f}, accuracy: {initial_val_accuracy:.2f}%"
    )
    print(
        f"Final validation loss: {final_val_loss:.4f}, accuracy: {final_val_accuracy:.2f}%"
    )
    print(
        f"Improvement: Loss {initial_val_loss - final_val_loss:.4f}, Accuracy {final_val_accuracy - initial_val_accuracy:.2f}%"
    )
    print(f"Model saved to: {best_model_path}")

    # Export training information to a log file
    log_file = os.path.splitext(output_model_path)[0] + "_training_log.txt"
    with open(log_file, "w") as f:
        f.write(f"Original model: {base_model_path}\n")
        f.write(f"Retrained model: {output_model_path}\n")
        f.write(f"Number of epochs: {num_epochs}\n")
        f.write(f"Classes: {class_names}\n")
        f.write(f"Training samples: {len(train_dataset)}\n")
        f.write(f"Validation samples: {len(val_dataset)}\n")
        f.write(
            f"Initial validation loss: {initial_val_loss:.4f}, accuracy: {initial_val_accuracy:.2f}%\n"
        )
        f.write(
            f"Final validation loss: {final_val_loss:.4f}, accuracy: {final_val_accuracy:.2f}%\n"
        )
        f.write(
            f"Improvement: Loss {initial_val_loss - final_val_loss:.4f}, Accuracy {final_val_accuracy - initial_val_accuracy:.2f}%\n"
        )

    print(f"Training log saved to: {log_file}")

    # Save updated model info
    model_info = {
        "num_classes": num_classes,
        "class_names": class_names,
        "class_mapping": train_dataset.class_to_idx,
        "image_size": image_size,
    }

    with open("model_info.json", "w") as f:
        json.dump(model_info, f)

    print("Updated model information saved to model_info.json")

    return model


if __name__ == "__main__":
    # Define paths
    base_model_path = (
        r"ML model\models\best_color_model.pth"  # Path to your pre-trained model
    )
    output_model_path = (
        r"ML model\models\retrained_color_model.pth"  # Path to save the new model
    )

    # Number of epochs for retraining
    num_epochs = 5
    # Retrain the model
    retrain_model(base_model_path, output_model_path, num_epochs)

    print("Script completed successfully!")
