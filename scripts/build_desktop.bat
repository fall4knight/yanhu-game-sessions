@echo off
REM Build desktop application packages using PyInstaller (Windows)

echo Building Yanhu Sessions desktop app...

REM Check if PyInstaller is installed
where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyInstaller not found. Install with: pip install pyinstaller
    exit /b 1
)

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build using spec file
echo Running PyInstaller...
pyinstaller yanhu.spec

REM Show results
echo.
echo Build complete!
echo.
echo Windows executable created at: dist\yanhu\yanhu.exe
echo You can run it by double-clicking yanhu.exe
echo.
echo NOTE: The built app does NOT include ffmpeg.
echo Users must install ffmpeg separately for video processing.
