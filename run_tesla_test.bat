@echo off
echo Testing Document Processor with Tesla Documents
echo =============================================
echo.

cd /d "%~dp0"

echo Running Python test script...
python test_tesla_extraction.py

echo.
echo Test completed. Press any key to exit.
pause >nul
