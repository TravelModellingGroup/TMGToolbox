@echo off
if exist "%EMMEPATH%/Python27/python.exe" (
    "%EMMEPATH%/Python27/python.exe" "%~dp0\build_toolbox.py" -c
) else (
    "%EMMEPATH%/Python37/python.exe" "%~dp0\build_toolbox.py" -c
)
