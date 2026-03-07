# Sesame — Modernized

Sesame — Modernized is a Python implementation of the SESAME nutrient economic evaluation method originally described in:

**St-Pierre, N.R., and D. Glamocic. 2000.**
Estimating unit costs of nutrients from market prices of feedstuffs.
*Journal of Dairy Science* 83:1402–1411.
https://doi.org/10.3168/jds.S0022-0302(00)75009-0

The software estimates the implicit economic value ("shadow price") of nutrients in feed ingredients using multiple regression. It allows dairy nutritionists to evaluate feed ingredient prices relative to their nutrient supply and identify ingredients that may be economically undervalued or overvalued.

---

## Features

• Modern graphical interface built with **Python** and **PySide6**
• Multiple preset nutrient systems for feed evaluation
• Automatic calculation of derived nutrient variables
• Estimation of nutrient shadow prices
• Feed value comparison (Predicted vs Actual price)
• Opportunity plots to identify undervalued feed ingredients
• Export of tables and charts for further analysis

---

## Input Data

The program reads a **CSV feed library** containing:

* Feed name
* Price ($/ton)
* Nutrient composition values

Typical nutrient columns may include:

* CP (Crude Protein)
* DE (Digestible Energy)
* NDF
* RUP
* Amino acid composition
* Fiber digestibility (NDFD)
* Starch
* Sugars

Additional derived nutrient variables are calculated automatically by the software.

---

## Output

Results are written to the **outputs/** folder and include:

• Feed value summary table
• Break-even nutrient value table
• Nutrient shadow prices
• Feed value bar chart (Actual vs Predicted price)
• Opportunity plot identifying undervalued or overvalued ingredients

---

## Running the Program

Install required packages:

```
pip install -r requirements.txt
```

Run the program:

```
python main.py
```

Alternatively, the program can be started using:

```
start_sesame.bat
```

---

## Folder Structure

SesameModernized

```
assets/        (icons and banner images)
models/        (nutrient calculations and estimator)
ui/            (graphical interface)

main.py        (program entry point)
requirements.txt
README.md
```

Additional folders used by the program:

```
data/raw/      (input feed libraries)
outputs/       (analysis results and charts)
```

---

## Acknowledgment

This software is inspired by the original **SESAME** program developed at
The Ohio State University.

The modern Python implementation was developed at the
**University of Nebraska–Lincoln**.

---

## License

This software is intended for research and educational use.
