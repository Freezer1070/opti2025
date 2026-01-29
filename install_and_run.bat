@echo off
setlocal

set PROJECT_DIR=%~dp0OmniPlayer2026
set OUTPUT_DIR=%PROJECT_DIR%\bin\Release\net8.0-windows\win-x64\publish
set EXE_PATH=%OUTPUT_DIR%\OmniPlayer2026.exe
set VLC_DLL=%OUTPUT_DIR%\libvlc.dll

if not exist "%PROJECT_DIR%\OmniPlayer2026.csproj" (
  echo Project not found: %PROJECT_DIR%\OmniPlayer2026.csproj
  pause
  exit /b 1
)

dotnet restore "%PROJECT_DIR%\OmniPlayer2026.csproj"
if errorlevel 1 (
  echo Restore failed.
  pause
  exit /b 1
)

dotnet publish "%PROJECT_DIR%\OmniPlayer2026.csproj" -c Release -r win-x64 -p:PublishSingleFile=false -p:SelfContained=true
if errorlevel 1 (
  echo Publish failed.
  pause
  exit /b 1
)

if not exist "%VLC_DLL%" (
  echo libvlc.dll not found in %OUTPUT_DIR%
  echo Ensure VideoLAN.LibVLC.Windows was restored and copied to output.
  pause
  exit /b 1
)

if not exist "%EXE_PATH%" (
  echo Executable not found: %EXE_PATH%
  pause
  exit /b 1
)

start "OmniPlayer 2026" "%EXE_PATH%"
endlocal
