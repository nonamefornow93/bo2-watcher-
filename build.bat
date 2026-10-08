@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   BO2 Achievement Toolkit - build
echo ============================================================
echo.

set "PY=python"
where %PY% >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH. Install Python 3.11+ first.
    exit /b 1
)

%PY% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller is not installed. Run:  python -m pip install pyinstaller
    exit /b 1
)

echo [1/3] Building the app with PyInstaller (onefolder, windowed)...
%PY% -m PyInstaller --noconfirm --clean --windowed --name BO2Toolkit ^
  --icon app.ico ^
  --add-data "bo2_icon.png;." ^
  --add-data "bo2_popup_sound.mp3;." ^
  --add-data "bo2_achievements.json;." ^
  --add-data "bo2_zombies_achievements.json;." ^
  --add-data "BO2 Zombies Achievements.txt;." ^
  --hidden-import psutil ^
  bo2_toolkit.py
if errorlevel 1 (
    echo.
    echo PyInstaller FAILED.
    exit /b 1
)

echo.
echo [2/3] Locating Inno Setup...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo WARNING: Inno Setup 6 not found - skipping the installer step.
    echo The portable app is ready at: dist\BO2Toolkit\BO2Toolkit.exe
    echo Install Inno Setup 6 to also produce BO2-Toolkit-Setup.exe.
    exit /b 0
)

echo [3/3] Building the installer with Inno Setup...
"%ISCC%" installer.iss
if errorlevel 1 (
    echo.
    echo Inno Setup FAILED.
    exit /b 1
)

echo.
echo ============================================================
echo   DONE
echo ============================================================
echo   Portable app : dist\BO2Toolkit\BO2Toolkit.exe
echo   Installer    : installer-output\BO2-Toolkit-Setup.exe
echo.
endlocal
