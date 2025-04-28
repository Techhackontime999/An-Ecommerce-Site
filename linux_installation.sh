#!/bin/bash

# Update the package list and upgrade all packages
echo "Updating package list and upgrading packages..."
sudo apt update && sudo apt upgrade -y
# Install necessary software packages
echo "Installing necessary software packages..."
SOFTWARE_LIST=(
    "graphviz graphviz-dev pkg-config libgraphviz-dev libjpeg-dev zlib1g-dev"
    "git"
    "build-essential"
    "gcc"
    "python3"
    "python3-pip"
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
echo "creating siteenv"
python3 -m venv siteenv
echo "activating siteenv"
source "siteenv/bin/activate"
echo "Now you are in siteenv"
cd "An-Ecommerce-Site"
echo "Installing software dependencies"
pip install -r "requirements.txt"
echo "Applying database migrations"
python manage.py "makemigrations"
python manage.py "migrate"
echo "creating default groups in software"
python manage.py "create_default_groups"
echo "creating now superuser enter below details"
python manage.py "createsuperuser"
echo "Software installation completed!"

echo "Now starting server..."
python manage.py runserver


