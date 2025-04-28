#!/bin/bash

# Update the package list and upgrade all packages
echo "Updating package list and upgrading packages..."
sudo apt update && sudo apt upgrade -y

# Install necessary software packages
echo "Installing software packages..."
SOFTWARE_LIST=(
    "curl"
    "git"
    "vim"
    "htop"
    "wget"
    "build-essential"
    "python3"
    "python3-pip"
    "nginx"
)

for SOFTWARE in "${SOFTWARE_LIST[@]}"; do
    echo "Installing $SOFTWARE..."
    sudo apt install -y $SOFTWARE
done

# Clean up unnecessary packages
echo "Cleaning up unnecessary packages..."
sudo apt autoremove -y

# Verify installation
echo "Verifying installed software..."
for SOFTWARE in "${SOFTWARE_LIST[@]}"; do
    if command -v $SOFTWARE &>/dev/null; then
        echo "$SOFTWARE is installed successfully."
    else
        echo "Error: $SOFTWARE installation failed."
    fi
done

echo "Software installation script completed!"
