import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
import os
from tqdm import tqdm
from sklearn.metrics import confusion_matrix, classification_report
import matplotlib.pyplot as plt
import numpy as np

from multiprocessing import freeze_support
if __name__ == '__main__':
    freeze_support() # Only needed if you plan to freeze the script

    # --- Configuration ---
    train_dir = 'data/dataset_split/train' # Path to your training data
    val_dir = 'data/dataset_split/val'   # Path to your validation data
    image_size = 200
    batch_size = 32
    num_epochs = 10
    learning_rate = 0.001
    load_pretrained = False  # Set to True to load a saved model
    pretrained_path = 'color_model.pth' # Path to your saved model file
    num_workers = 0 # Set to 0 for Windows multiprocessing issues

    # --- Determine Device ---
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print("CUDA is available. Training on GPU.")
    else:
        device = torch.device("cpu")
        print("CUDA not available. Training on CPU.")

    # --- Transformations ---
    train_transforms = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transforms = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # --- Load Datasets ---
    train_dataset = datasets.ImageFolder(train_dir, transform=train_transforms)
    val_dataset = datasets.ImageFolder(val_dir, transform=val_transforms)

    # --- Create Data Loaders ---
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    # --- Get Class Information ---
    class_names = train_dataset.classes
    num_classes = len(class_names)
    print(f"Valid classes detected: {class_names}")
    print(f"Number of classes: {num_classes}")
    print(f"Class mapping: {train_dataset.class_to_idx}")

    # --- Define the Simple Color CNN model ---
    class SimpleColorCNN(nn.Module):
        def __init__(self, num_classes):
            super(SimpleColorCNN, self).__init__()
            self.conv1 = nn.Conv2d(3, 16, kernel_size=3, stride=1, padding=1)
            self.relu1 = nn.ReLU()
            self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)
            self.conv2 = nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1)
            self.relu2 = nn.ReLU()
            self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)
            self.gap = nn.AdaptiveAvgPool2d((1, 1)) # Global Average Pooling
            self.fc = nn.Linear(32, num_classes)

        def forward(self, x):
            x = self.pool1(self.relu1(self.conv1(x)))
            x = self.pool2(self.relu2(self.conv2(x)))
            x = self.gap(x)
            x = x.view(x.size(0), -1)
            x = self.fc(x)
            return x

    # --- Initialize the model and load pretrained weights if specified ---
    model = SimpleColorCNN(num_classes).to(device)
    print(f"Using device: {device}")

    if load_pretrained:
        try:
            model.load_state_dict(torch.load(pretrained_path, map_location=device)) # Ensure loading to the correct device
            print(f"Loaded pretrained model from: {pretrained_path}")
        except FileNotFoundError:
            print(f"Pretrained model not found at: {pretrained_path}. Training from scratch.")

    # --- Define loss function and optimizer ---
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # --- Training loop ---
    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        total_train = 0
        train_progress = tqdm(enumerate(train_loader), total=len(train_loader), desc=f"Epoch {epoch+1}/{num_epochs} - Training")
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

            train_progress.set_postfix({'loss': f'{loss.item():.4f}'})

        train_loss = train_loss / total_train
        train_accuracy = 100 * train_correct / total_train
        print(f'Epoch {epoch+1}/{num_epochs}, Training Loss: {train_loss:.4f}, Training Accuracy: {train_accuracy:.2f}%')

        # --- Validation loop ---
        model.eval()
        val_loss = 0.0
        val_correct = 0
        total_val = 0
        all_labels = []
        all_predictions = []
        val_progress = tqdm(enumerate(val_loader), total=len(val_loader), desc=f"Epoch {epoch+1}/{num_epochs} - Validation")
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

                all_labels.extend(labels.cpu().numpy())
                all_predictions.extend(predicted.cpu().numpy())

                val_progress.set_postfix({'loss': f'{loss.item():.4f}'})

        val_loss = val_loss / total_val
        val_accuracy = 100 * val_correct / total_val
        print(f'Epoch {epoch+1}/{num_epochs}, Validation Loss: {val_loss:.4f}, Validation Accuracy: {val_accuracy:.2f}%')

    print("Training finished!")

    # --- Calculate and Display Confusion Matrix and Classification Report ---
    cm = confusion_matrix(all_labels, all_predictions)
    print("\nConfusion Matrix:")
    print(cm)

    cr = classification_report(all_labels, all_predictions, target_names=class_names)
    print("\nClassification Report:")
    print(cr)

    # --- Optional: Plot the Confusion Matrix ---
    plt.figure(figsize=(8, 8))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion Matrix')
    plt.colorbar()
    tick_marks = np.arange(len(class_names))
    plt.xticks(tick_marks, class_names, rotation=45)
    plt.yticks(tick_marks, class_names)

    thresh = cm.max() / 2.
    for i, j in np.ndindex(cm.shape):
        plt.text(j, i, f'{cm[i, j]}', horizontalalignment="center", color="white" if cm[i, j] > thresh else "black")

    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.show()

    # Save the trained model
    torch.save(model.state_dict(), 'color_model_trained_further.pth')