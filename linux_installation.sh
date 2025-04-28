#!/bin/bash
# Define Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Welcome To Shop-Seed >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>${NC}"
echo ""

# Update the package list and upgrade all packages
echo "********************************************************************************************************************"
echo -e "${YELLOW}Updating package list and upgrading packages...${NC}"
echo "********************************************************************************************************************"
sudo apt update && sudo apt upgrade -y

# Install necessary software packages
echo "********************************************************************************************************************"
echo -e "${YELLOW}Installing necessary software packages...${NC}"
echo "********************************************************************************************************************"

SOFTWARE_LIST=(
    "graphviz"
    "pkg-config"
    "libgraphviz-dev"
    "libjpeg-dev"
    "zlib1g-dev"
    "git"
    "build-essential"
    "gcc"
    "python3"
    "python3-pip"
    "python3.10-venv"
)

for SOFTWARE in "${SOFTWARE_LIST[@]}"; do
    echo -e "${BLUE}Installing $SOFTWARE...${NC}"
    sudo apt install -y $SOFTWARE
done

# Clean up unnecessary packages
echo "********************************************************************************************************************"
echo -e "${YELLOW}Cleaning up unnecessary packages...${NC}"
echo "********************************************************************************************************************"
sudo apt autoremove -y

# Verifying installed software
echo "********************************************************************************************************************"
echo -e "${YELLOW}Verifying installed software...${NC}"
echo "********************************************************************************************************************"
for SOFTWARE in "${SOFTWARE_LIST[@]}"; do
    if dpkg -s $SOFTWARE &>/dev/null; then
        echo -e "${GREEN}$SOFTWARE is installed successfully.${NC}"
    else
        echo -e "${RED}Error: $SOFTWARE installation failed.${NC}"
    fi
done


# Create virtual environment
echo "********************************************************************************************************************"
echo -e "${YELLOW}Creating siteenv...${NC}"
echo "********************************************************************************************************************"
python3 -m venv siteenv

# Activate virtual environment
echo "********************************************************************************************************************"
echo -e "${YELLOW}Activating siteenv...${NC}"
echo "********************************************************************************************************************"
source "siteenv/bin/activate"

echo "********************************************************************************************************************"
echo -e "${GREEN}Now you are in siteenv.${NC}"
echo "********************************************************************************************************************"

# Go to project folder
cd "An-Ecommerce-Site"

# Install project dependencies
echo "********************************************************************************************************************"
echo -e "${YELLOW}Installing software dependencies...${NC}"
echo "********************************************************************************************************************"
pip install -r "requirements.txt"

# Apply migrations
echo "********************************************************************************************************************"
echo -e "${YELLOW}Applying database migrations...${NC}"
echo "********************************************************************************************************************"
python manage.py "makemigrations"
python manage.py "migrate"

# Create default groups
echo "********************************************************************************************************************"
echo -e "${YELLOW}Creating default groups in software...${NC}"
echo "********************************************************************************************************************"
python manage.py "create_default_groups"

# Create superuser
echo "********************************************************************************************************************"
echo -e "${YELLOW}Now creating superuser, please enter the following details:${NC}"
echo "********************************************************************************************************************"
python manage.py "createsuperuser"

# Completed
echo "********************************************************************************************************************"
echo -e "${GREEN}Software installation completed!${NC}"
echo "********************************************************************************************************************"

# Start server
echo "********************************************************************************************************************"
echo -e "${YELLOW}Now starting server...${NC}"
echo "********************************************************************************************************************"
python manage.py runserver
