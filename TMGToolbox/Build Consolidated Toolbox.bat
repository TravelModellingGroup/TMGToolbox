@echo off
setlocal

REM Check if the Python executables exist
if exist "%EMMEPATH%\Python27\python.exe" (
    set "EMME_PYTHON=%EMMEPATH%\Python27\python.exe"
    goto BuildToolbox
) else if exist "%EMMEPATH%\Python37\python.exe" (
    set "EMME_PYTHON=%EMMEPATH%\Python37\python.exe"
    goto BuildToolbox
) else if exist "%EMMEPATH%\Python311\python.exe" (
    set "EMME_PYTHON=%EMMEPATH%\Python311\python.exe"
    goto BuildToolbox
) else (
    goto Error
)

:BuildToolbox
REM Execute build_toolbox.py using the selected Python environment
echo Found EMME Python environment at %EMME_PYTHON% & echo.
"%EMME_PYTHON%" "%~dp0\build_toolbox.py" -c
goto End

:Error
echo Cannot find the EMME Python environment
goto End

:End
