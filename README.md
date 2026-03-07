# Sesame Modernized

A modern Python implementation of the **SESAME nutrient economics method** for evaluating feed ingredient prices based on nutrient composition.

This application helps nutritionists and feed analysts estimate nutrient shadow prices, compare actual vs. predicted feed values, and identify potential purchase opportunities.

## What the application does

- Loads a feed library from CSV
- Computes derived nutrient variables
- Estimates nutrient shadow prices
- Calculates break-even nutrient values
- Compares actual feed prices against model-predicted prices
- Exports analysis tables and charts to the `outputs/` folder

## Repository layout

```text
.
├── SesameModernized/         # Main application package
│   ├── main.py               # App entry point (GUI)
│   ├── requirements.txt      # Package-local dependencies
│   ├── models/               # Nutrient and estimator logic
│   ├── ui/                   # PySide6 GUI
│   └── assets/               # Icons and branding assets
├── data/raw/                 # Example feed library CSV files
├── outputs/                  # Generated result files/charts
├── run_sesame.py             # Root launcher wrapper
├── start_sesame.bat          # Windows launcher script
└── requirements.txt          # Root dependencies
```

## Dependencies

The project is built with Python and the following libraries:

- `PySide6` (GUI)
- `pandas` (data handling)
- `numpy` (numerical calculations)
- `matplotlib` (plots/charts)

## Installation (Windows)

### 1) Install Python

- Download and install **Python 3.10+** from: https://www.python.org/downloads/windows/
- During installation, enable **“Add Python to PATH”**.

### 2) Open a terminal in the repository folder

Use **Command Prompt** or **PowerShell**, then change into the project directory:

```powershell
cd C:\path\to\sesame-modernized
```

### 3) (Recommended) Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 4) Install dependencies

Install from the root requirements file:

```powershell
pip install -r requirements.txt
```

> Note: The Windows launcher (`start_sesame.bat`) installs from `SesameModernized\requirements.txt` automatically before starting the app.

## Running the application on Windows

You can start the application using either method below.

### Option A: Double-click launcher

- Double-click `start_sesame.bat`

### Option B: Run from terminal

From the repository root:

```powershell
python run_sesame.py
```

Or run the package entry point directly:

```powershell
python SesameModernized\main.py
```

## Typical workflow

1. Launch the app.
2. Click **Run Estimator (CSV...)**.
3. Select a feed library CSV (for example, from `data/raw/`).
4. Review outputs generated in the `outputs/` folder:
   - summary tables
   - break-even tables
   - nutrient shadow price tables
   - charts (including opportunity plots)

## Troubleshooting (Windows)

- **`python` is not recognized**
  - Reinstall Python and ensure **Add Python to PATH** is selected.

- **Package installation fails**
  - Upgrade pip and retry:
    ```powershell
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

- **GUI does not open / closes immediately**
  - Run from terminal (`python run_sesame.py`) to view error output.

## Background

The method implemented here is based on:

**St-Pierre, N.R., and D. Glamocic. (2000).**
*Estimating unit costs of nutrients from market prices of feedstuffs.*
Journal of Dairy Science, 83:1402–1411.
https://doi.org/10.3168/jds.S0022-0302(00)75009-0

## License

This project is intended for research and educational use.
