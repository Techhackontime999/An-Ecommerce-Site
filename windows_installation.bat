@echo off
:: Define Colors (only for PowerShell, cmd doesn't support full colors easily)
:: But using simple echo texts for now

echo.
echo.<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Welcome To Shop-Seed >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
echo.

echo ********************************************************************************************************************
echo Updating Python packages and setting up the environment...
echo ********************************************************************************************************************

:: Check Python Installation
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed. Please install Python 3.x first.
    pause
    exit /b
)

:: Check pip Installation
pip --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Error: pip is not installed. Please install pip first.
    pause
    exit /b
)

:: Install virtualenv if not available
pip show virtualenv >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Installing virtualenv...
    pip install virtualenv
)

:: Create virtual environment
echo ********************************************************************************************************************
echo Creating virtual environment: siteenv
echo ********************************************************************************************************************
python -m venv siteenv

:: Activate virtual environment
echo ********************************************************************************************************************
echo Activating virtual environment...
echo ********************************************************************************************************************
call siteenv\Scripts\activate.bat

:: Navigate to project folder
cd An-Ecommerce-Site

:: Install project dependencies
echo ********************************************************************************************************************
echo Installing project dependencies...
echo ********************************************************************************************************************
pip install -r requirements.txt

:: Apply migrations
echo ********************************************************************************************************************
echo Applying database migrations...
echo ********************************************************************************************************************
python manage.py makemigrations
python manage.py migrate

:: Create default groups
echo ********************************************************************************************************************
echo Creating default groups...
echo ********************************************************************************************************************
python manage.py create_default_groups

:: Create superuser
echo ********************************************************************************************************************
echo Now creating superuser, please enter the following details:
echo ********************************************************************************************************************
python manage.py createsuperuser

:: Completed
echo ********************************************************************************************************************
echo Software installation completed!
echo ********************************************************************************************************************

:: Start server
echo ********************************************************************************************************************
echo Now starting Django server...
echo ********************************************************************************************************************
python manage.py runserver

pause

