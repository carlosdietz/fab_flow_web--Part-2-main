@echo off
echo Fab Flow Game Simulation Runner
echo ==============================
echo.

echo This script will run simulations of the Fab Flow game to analyze strategies.
echo.

echo Options:
echo 1. Run simple simulation (CSV output)
echo 2. Run advanced simulation (Database + Analysis)
echo 3. Run smaller test simulation (100 runs)
echo 4. Exit
echo.

set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo.
    echo Running simple simulation with 3,000 runs per strategy...
    echo (This will take some time to complete)
    echo.
    python simple_simulations.py
    echo.
    echo Results saved to simulation_results.csv
    echo.
    pause
) else if "%choice%"=="2" (
    echo.
    echo Running advanced simulation with 3,000 runs per strategy...
    echo (This will take some time to complete)
    echo.
    python run_simulations.py
    echo.
    echo Results saved to simulation_results.db and visualization files
    echo.
    pause
) else if "%choice%"=="3" (
    echo.
    echo Running test simulation with 100 runs per strategy...
    echo.
    python simple_simulations.py --simulations=100 --output=test_simulation_results.csv
    echo.
    echo Test results saved to test_simulation_results.csv
    echo.
    pause
) else if "%choice%"=="4" (
    echo Exiting...
) else (
    echo Invalid choice. Please run the script again.
    pause
)
