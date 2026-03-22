@echo off
pyinstaller --noconfirm --onefile --windowed --hidden-import=pandas --hidden-import=openpyxl Alquileres.py
pause
