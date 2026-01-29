@echo off
setlocal

set PROJECT_DIR=%~dp0OmniPlayer2026
set OUTPUT_DIR=%PROJECT_DIR%\bin\Release\net8.0-windows\win-x64\publish

dotnet publish "%PROJECT_DIR%\OmniPlayer2026.csproj" -c Release -r win-x64 -p:PublishSingleFile=true -p:SelfContained=true
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

start "OmniPlayer 2026" "%OUTPUT_DIR%\OmniPlayer2026.exe"
endlocal
