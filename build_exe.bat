@echo off
setlocal

set PROJECT_DIR=%~dp0OmniPlayer2026
set OUTPUT_DIR=%PROJECT_DIR%\bin\Release\net8.0-windows\win-x64\publish

if not exist "%PROJECT_DIR%\OmniPlayer2026.csproj" (
  echo Project not found: %PROJECT_DIR%\OmniPlayer2026.csproj
  exit /b 1
)

dotnet restore "%PROJECT_DIR%\OmniPlayer2026.csproj"
if errorlevel 1 (
  echo Restore failed.
  exit /b 1
)

dotnet publish "%PROJECT_DIR%\OmniPlayer2026.csproj" -c Release -r win-x64 -p:PublishSingleFile=true -p:SelfContained=true
if errorlevel 1 (
  echo Publish failed.
  exit /b 1
)

echo Build complete: %OUTPUT_DIR%\OmniPlayer2026.exe
endlocal
