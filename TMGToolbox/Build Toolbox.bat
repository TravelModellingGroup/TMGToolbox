@echo off
if exist "%EMMEPATH%/Python27/python.exe" (
    "%EMMEPATH%/Python27/python.exe" "%~dp0\build_toolbox.py"
) else (
    "%EMMEPATH%/Python37/python.exe" "%~dp0\build_toolbox.py"
)
