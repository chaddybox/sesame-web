@echo off

echo Starting Sesame...

REM Install required Python packages
pip install -r SesameModernized\requirements.txt

REM Launch the program
python SesameModernized\main.py

pause