# Species Observation and Reporting Tool

This Python project enables you to analyze and report species observations using data from external sources, including **Waarnemingen.be**, **Wikipedia**, and **Observation.org**. The tool generates detailed reports in PDF format, maps observations, and performs biodiversity and seasonal analyses for selected species.

## Features

- **Scientific Name Lookup**: Retrieve scientific names for species using Wikipedia.
- **Species Information**: Fetch species details, rarity, descriptions, and recent observations.
- **PDF Report Generation**: Generate a professional species report in PDF format.
- **Map Observations**: Visualize recent species observations on an interactive map.
- **Seasonal Analysis**: Analyze seasonal observation patterns for a given species and year.
- **Biodiversity Analysis**: Calculate biodiversity indices (e.g., Shannon and Simpson indices) for species richness and evenness.
- **ChatGPT Integration**: Use AI to derive insights and context for scientific data.

---

## Requirements

This project requires the following Python packages:

- `requests`
- `beautifulsoup4`
- `folium`
- `fpdf`
- `Pillow`
- `matplotlib`
- `numpy`
- `openai`
- `python-dotenv`

Ensure these dependencies are installed in your environment.