@echo off
REM Build a standalone Windows executable for Barcode Manager.
REM Output: dist\BarcodeManager.exe

setlocal
pushd "%~dp0"

echo === Regenerating icon ===
py -3 tools\make_icon.py || goto :fail

echo === Building EXE ===
py -3 -m PyInstaller --noconfirm BarcodeManager.spec || goto :fail

echo.
echo === Done ===
echo Built: dist\BarcodeManager.exe
popd
exit /b 0

:fail
echo BUILD FAILED
popd
exit /b 1
