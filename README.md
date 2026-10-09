# Reptiles & Amphibians – Brabant Wallon

A Python tool that retrieves species observations for **Walloon Brabant (Belgium)**, cleans the data, and turns it into seasonal charts, an interactive map and an automated species report.

Search for a species by name and get a clean dataset and ready-to-read results, instead of scrolling through raw observation records.





## What it does

- **Retrieves** observations for a chosen reptile or amphibian species in Walloon Brabant
- **Cleans and structures** the records with Pandas
- **Analyses** seasonal patterns (when in the year the species is observed)
- **Maps** observation locations in an interactive HTML map
- **Reports** the results in an automated PDF species report
- **Automates** the data flow with a Node-RED workflow

Example species included in this repo: Common Frog, Fire Salamander and Smooth Newt.

## Tech stack

Python · Pandas · Matplotlib · Jupyter Notebook · Node-RED

## Project structure

```
Reptiles_and_amphibians-Brabant_Wallon
├── Natuurspotter/            # Python package: species retrieval and processing
│   ├── __init__.py
│   └── species.py
├── Node-Red/                 # Node-RED flow and screenshots
│   ├── flows (1).json
│   └── pic1.png … pic4.png
├── data/
│   ├── observations_08_2021.csv      # Example cleaned observations
│   ├── observations_map.html         # Interactive map
│   ├── seasonal_observations.png     # Seasonal chart
│   ├── species_report.pdf            # Automated species report
│   └── *.jpg                         # Species photos
├── demo.ipynb                # Walkthrough notebook
├── setup.py
└── License.txt
```

## Getting started

```bash
git clone https://github.com/mazan13126114-cell/Reptiles_and_amphibians-Brabant_Wallon.git
cd Reptiles_and_amphibians-Brabant_Wallon
pip install -e .
```

Then open **`demo.ipynb`** in Jupyter for a step-by-step example: choose a species, retrieve its observations, and generate the chart, map and report.

## Results

| Output | File |
| --- | --- |
| Cleaned observations (CSV) | [`data/observations_08_2021.csv`](data/observations_08_2021.csv) |
| Seasonal chart | [`data/seasonal_observations.png`](data/seasonal_observations.png) |
| Interactive map (download and open in a browser) | [`data/observations_map.html`](data/observations_map.html) |
| Species report | [`data/species_report.pdf`](data/species_report.pdf) |

The number of observations depends on the species searched, so results differ from one species to the next.

## Node-RED workflow

The `Node-Red/` folder contains the flow used to automate the process, with screenshots (`pic1.png` – `pic4.png`). Import `flows (1).json` into Node-RED to explore it.

## What I learned

- Building a small end-to-end data pipeline: collection, cleaning, analysis, visualisation and reporting
- Structuring reusable Python code as an installable package
- Automating a data workflow with Node-RED

## Author

**Mazan Ali** – Data Science student at Thomas More University, Antwerp
[GitHub](https://github.com/mazan13126114-cell) · mazan13126114@gmail.com

## License

See [`License.txt`](License.txt).
