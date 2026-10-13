import os
import re
import csv
import time
import hashlib
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urljoin, quote_plus

import requests
import wikipedia
import folium
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from folium.plugins import MarkerCluster
from fpdf import FPDF
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


#-----------------------------------------------------------------------------------------------------------------------
# Settings
# observations.be is the French-language version of waarnemingen.be: same database, same species IDs.
#-----------------------------------------------------------------------------------------------------------------------

BASE_URL = "https://observations.be"
WAARNEMINGEN_URL = "https://waarnemingen.be"
OBSERVATION_ORG_URL = "https://observation.org"
REQUEST_TIMEOUT = 15  # seconds

# The group name is shown in the site's language, so accept French, Dutch and English
REPTILE_GROUP_NAMES = {"reptiles et amphibiens", "reptielen en amfibieen", "reptiles and amphibians"}

load_dotenv()  # reads OPENAI_API_KEY (and optionally OPENAI_MODEL) from a .env file


def fetch(url):
    """Download a page with a timeout and raise an error for HTTP failures (404, 500, ...)."""
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response


def make_driver(headless=True):
    """Start Chrome for Selenium. Headless means no browser window opens."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def strip_accents(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def clean_text(text):
    if not isinstance(text, str):
        return text
    return unicodedata.normalize('NFKD', text).encode('latin-1', 'ignore').decode('latin-1')



#------------------------------------------------------------------------------------------------------------------------
#------------------------------Custom PDF class with header and footer---------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------



class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, clean_text('Species Report'), align='C', ln=True)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, clean_text(f'Page {self.page_no()}'), align='C')
        
        
        
        
#----------------------------------------------------------------------------------------------------------------------------
#----------------------Extract scientific name from Wikipedia page for given common name--------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------



def get_scientific_name_from_common(common_name):
    try:
        wiki_page = wikipedia.page(common_name)
        soup = BeautifulSoup(wiki_page.html(), "html.parser")

        italic_bold = soup.select_one("i b")
        if italic_bold:
            sci_name = italic_bold.text.strip()
        else:
            italic = soup.select_one("i")
            sci_name = italic.text.strip() if italic else None

        if sci_name and "." in sci_name.split()[0]:
            genus_abbreviation = sci_name.split()[0].strip(".")
            first_para = soup.find("p").text
            words = first_para.split()
            for word in words:
                if word.startswith(genus_abbreviation) and word.isalpha():
                    sci_name = sci_name.replace(genus_abbreviation + ".", word, 1)
                    break

        return sci_name
    except Exception:
        return None
    
    
#----------------------------Find the species ID on waarnemingen.be-----------------------------


def get_species_id(common_name):
    """Search waarnemingen.be for a species name and return its numeric ID (or None)."""
    common_name = common_name.strip()
    url = f"{WAARNEMINGEN_URL}/species/search/?q={quote_plus(common_name)}"
    print(f"Looking up species ID for: {common_name}")

    # Case-insensitive match, so "common frog" finds "Common Frog"
    upper, lower = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
    xpath = (
        f'//td[translate(@data-sort-value, "{upper}", "{lower}")'
        f' = "{common_name.lower()}"]/a'
    )

    driver = None
    try:
        driver = make_driver()
        driver.get(url)
        link = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
        match = re.search(r"/species/(\d+)/", link.get_attribute("href"))
        return match.group(1) if match else None
    except Exception as e:
        print(f"Could not find '{common_name}' on {WAARNEMINGEN_URL}: {e}")
        return None
    finally:
        if driver:
            driver.quit()  # always close the browser, even after an error


#--------------------------------------------------------------------------------------------------------
#---------------Generate comprehensive species report with observations and save as PDF---------------------------
#----------------specie_id is used to get the desired link for every unique specie----------------------
#----------------------------------------------------------------------------------------------------------------


def get_species_info(species_id, common_name, scientific_name):
    today = datetime.today().date()
    start_date = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    rarity, image_url = "Unknown", None

    try:
        page_response = fetch(f"{BASE_URL}/species/{species_id}/")
        soup = BeautifulSoup(page_response.content, "html.parser")
        rarity_span = soup.select_one(".pull-right span.hidden-sm")
        if rarity_span:
            rarity = rarity_span.text.strip()
    except Exception as e:
        print(f"Could not read rarity: {e}")

    try:
        resp = fetch(f"{BASE_URL}/species/{species_id}/photos/")
        soup = BeautifulSoup(resp.content, "html.parser")
        img_tag = soup.select_one("figure.lightbox-gallery img")
        if img_tag and img_tag.get("src"):
            image_url = urljoin(BASE_URL, img_tag["src"])  # works for relative and full links
    except Exception as e:
        print(f"Could not find a photo: {e}")

    try:
        description = wikipedia.summary(common_name, sentences=3)
    except Exception as e:
        print(f"Could not get a Wikipedia summary: {e}")
        description = "No Wikipedia summary available."

    observations = []
    try:
        obs_url = (
            f"{BASE_URL}/countries/division/25/observations/"
            f"?date_after={start_date}&date_before={end_date}&species={species_id}"
            f"&species_group=3&country_division=25"
        )
        resp = fetch(obs_url)
        soup = BeautifulSoup(resp.content, "html.parser")
        table = soup.find("table", class_="table-bordered")
        if table:
            rows = table.find("tbody").find_all("tr")[:10]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 5:
                    observations.append({
                        "date": cols[0].text.strip(),
                        "count": ''.join(filter(str.isdigit, cols[2].text.strip())) or "1",
                        "location": cols[3].text.strip(),
                        "observer": cols[4].text.strip()
                    })
    except Exception as e:
        print(f"Could not read recent observations: {e}")

    os.makedirs("data", exist_ok=True)
    filename = f"data/{common_name.replace(' ', '_')}_report.pdf"
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, clean_text(f"Common Name: {common_name}"), ln=True)
    pdf.cell(0, 10, clean_text(f"Scientific Name: {scientific_name}"), ln=True)
    pdf.cell(0, 10, clean_text(f"Rarity: {rarity}"), ln=True)
    pdf.multi_cell(0, 10, clean_text(f"Description: {description}"))
    pdf.cell(0, 10, "-" * 60, ln=True)

    if image_url:
        try:
            img_data = fetch(image_url).content
            img_path = f"data/{common_name.replace(' ', '_')}.jpg"
            with open(img_path, "wb") as f:
                f.write(img_data)
            pdf.image(img_path, w=100)
        except Exception as e:
            print(f"Could not add the photo to the PDF: {e}")

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, clean_text("Recent Observations:"), ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(40, 10, "Date", 1)
    pdf.cell(25, 10, "Count", 1)
    pdf.cell(75, 10, "Location", 1)
    pdf.cell(50, 10, "Observer", 1, ln=True)

    if observations:
        for obs in observations:
            pdf.cell(40, 10, clean_text(obs['date']), 1)
            pdf.cell(25, 10, clean_text(obs['count']), 1)
            pdf.cell(75, 10, clean_text(obs['location'][:30]), 1)
            pdf.cell(50, 10, clean_text(obs['observer'][:25]), 1, ln=True)
    else:
        pdf.cell(0, 10, "No recent observations found.", ln=True)

    pdf.output(filename)
    print(f"\n PDF saved to {filename}")
    
    
#-----------------------------------------------------------------------------------------
#---------------Main function to generate species information report----------------------------
#-----------------------------------------------------------------------------------------
def get_group_name(species_id):
    try:
        response = fetch(f"{BASE_URL}/species/{species_id}/")
        soup = BeautifulSoup(response.content, "html.parser")

        # Get the outermost btn-group with species hierarchy
        btn_group = soup.find("div", class_="btn-group btn-group-sm")
        if btn_group:
            # First <a> typically contains the group name
            first_a = btn_group.find("a")
            if first_a:
                return first_a.get_text(strip=True)
    except Exception as e:
        print("Error while scraping group name:", e)
    return "Unknown"






def species_info(common_name):
    print(f" Looking up species for: {common_name}")

    scientific_name = get_scientific_name_from_common(common_name)
    if not scientific_name:
        print(" Could not get scientific name from Wikipedia.")
        return

    species_id = get_species_id(common_name)
    if not species_id:
        print(" Could not find species ID on website.")
        return

    group_name = get_group_name(species_id)
    print(f" Detected group: {group_name}")

    if strip_accents(group_name).lower() not in REPTILE_GROUP_NAMES:
        print(f"⚠️  Group '{group_name}' is not supported. Only 'Reptiles and Amphibians' are allowed.")
        return

    get_species_info(species_id, common_name, scientific_name)




#---------------------------------------------------------------------------------------
#------------Get common and scientific names for a species ID from observation.org-------------
#---------------------------------------------------------------------------------------


def get_species_names(species_id):
    url = f"{OBSERVATION_ORG_URL}/species/{species_id}/"
    try:
        resp = fetch(url)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract common name
        common_name_tag = soup.select_one("span.species-common-name")
        common_name = common_name_tag.text.strip() if common_name_tag else None

        # Extract scientific name
        scientific_name_tag = soup.select_one("i.species-scientific-name")
        scientific_name = scientific_name_tag.text.strip() if scientific_name_tag else None

        if common_name and scientific_name:
            return f"{common_name} ({scientific_name})"
        elif scientific_name:
            return scientific_name
        elif common_name:
            return common_name
        else:
            return f"Species ID: {species_id}"
    except Exception as e:
        print(f"Error fetching species name for ID {species_id}: {e}")
        return f"Species ID: {species_id}"

#--------------------------------------------------------------------------------------
#------------Generate an interactive map showing species observations----------------------
#--------------------------------------------------------------------------------------


def observations_map(day=None):
    if not day:
        day = datetime.today().strftime("%Y-%m-%d")

    geojson_url = (
        f"{WAARNEMINGEN_URL}/countries/division/25/observations/"
        f"?date_after={day}&date_before={day}&species_group=3&country_division=25&geojson=true"
    )
    print(f"Using GeoJSON URL: {geojson_url}")

    try:
        geojson = fetch(geojson_url).json()

        fmap = folium.Map(location=[50.85, 4.35], zoom_start=8)
        cluster = MarkerCluster().add_to(fmap)
        species_cache = {}

        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [None, None])
            lon, lat = coords if len(coords) == 2 else (None, None)

            if lat is None or lon is None:
                continue

            species_id = str(props.get("species-id", "Unknown"))
            if species_id not in species_cache:
                species_cache[species_id] = get_species_names(species_id)

            popup_text = species_cache[species_id]
            # Same colour for every observation of the same species
            marker_color = "#" + hashlib.md5(species_id.encode()).hexdigest()[:6]

            folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                color=marker_color,
                fill=True,
                fill_opacity=0.7,
                popup=popup_text
            ).add_to(cluster)

        os.makedirs("data", exist_ok=True)
        map_path = "data/observations_map.html"
        fmap.save(map_path)
        print(f"Map saved to {map_path}")

    except Exception as e:
        print(f"Error generating map: {e}")
        
        

#--------------------------------------------------------------------------------------
#------------Seasonal analysis----------------------
#--------------------------------------------------------------------------------------


def month_to_season(month_abbr):
    seasons = {
        "jan": "Winter", "feb": "Winter", "dec": "Winter",
        "mar": "Spring", "apr": "Spring", "may": "Spring",
        "jun": "Summer", "jul": "Summer", "aug": "Summer",
        "sep": "Autumn", "oct": "Autumn", "nov": "Autumn"
    }
    return seasons.get(month_abbr.lower(), None)

def ask_chatgpt(prompt):
    """Ask an OpenAI model for a short explanation. Returns None if no API key is set or the call fails."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OPENAI_API_KEY found, so the AI explanation is skipped.")
        return None
    try:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        print(f"\nAsking {model} for an explanation...")
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides scientific explanations."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI request failed: {e}")
        return None

#------------------------------------Main Function seasonal_analysis-------------------------

def seasonal_analysis(species_name, year):
    print(f" Analyzing seasonality for {species_name} in {year}...")

    driver = make_driver()

    try:
        # Step 1: Search species
        search_url = f"{OBSERVATION_ORG_URL}/search/?q={quote_plus(species_name)}"
        driver.get(search_url)
        time.sleep(2)

        species_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='/species/']")
        candidates = []
        for link in species_links:
            href = link.get_attribute("href") or ""
            match = re.search(r'/species/(\d+)/?$', href)
            if match:
                candidates.append((link.text.strip().lower(), match.group(1)))

        # Prefer the result whose name matches the search, instead of blindly taking the first link
        wanted = species_name.strip().lower()
        species_id = next((sid for text, sid in candidates if wanted in text), None)
        if species_id is None and candidates:
            species_id = candidates[0][1]
            print(f" No exact name match, using the first search result (ID {species_id}).")

        if not species_id:
            print(" Species ID not found.")
            return

        stats_url = f"{OBSERVATION_ORG_URL}/species/{species_id}/statistics/?year={year}"
        driver.get(stats_url)
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        table = soup.find("table", class_="chart-table")
        if not table:
            print(" Stats table not found.")
            return

        table_rows = table.find_all("tr")[1:]
        seasonal_counts = defaultdict(int)

        for row in table_rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                month_name = cols[0].text.strip()
                obs = re.sub(r"\D", "", cols[1].text)  # keep digits only ("1,234" or "1 234" -> "1234")
                month_abbr = month_name[:3].lower()
                season = month_to_season(month_abbr)

                if season and obs.isdigit():
                    seasonal_counts[season] += int(obs)

        if not seasonal_counts:
            print("No valid seasonal data found.")
            return

        seasons = ["Winter", "Spring", "Summer", "Autumn"]
        values = [seasonal_counts.get(season, 0) for season in seasons]

        plt.figure(figsize=(8, 5))
        plt.bar(seasons, values, color='teal')
        plt.title(f"{species_name} Observations by Season in {year}")
        plt.ylabel("Number of Observations")
        plt.tight_layout()
        os.makedirs("data", exist_ok=True)
        plt.savefig("data/seasonal_observations.png")
        plt.close()
        print("Graph saved as data/seasonal_observations.png")

        print("\n Observations by Season:")
        for s, v in zip(seasons, values):
            print(f"{s:>8}  : {v}")

        # Ensure the values list is not empty and handle edge cases
        if all(value == 0 for value in values):
            print("No observations recorded for any season.")
            return

        least_season = seasons[values.index(min(values))]
        prompt = (
            f"Why is the species '{species_name}' observed less in {least_season.lower()} in Brabant wallon? "
            f"Consider seasonal activity, behavior, and environmental conditions."
        )

        # ---------------- Call ChatGPT for explanation
        result = ask_chatgpt(prompt)
        if result:
            print("\nAI explanation:")
            print(result)

    except Exception as e:
        print(f" Error: {e}")
    finally:
        driver.quit()
        
#--------------------------------------------------------------------------------------------
#----------------Analyze biodiversity by scraping species observations for a given month/year----------
#--------------------------------------------------------------------------------------------


def biodiversity_analysis(month=None, year=None):
    now = datetime.now()
    month = int(month or now.month)
    year = int(year or now.year)

    start_date = f"{year}-{month:02}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02}-01"

    url = f"{BASE_URL}/countries/division/25/species/?species_group_id=3&filter_month={month}&filter_year={year}&include_exotic_and_extinct=on"
    print(f"Scraping live page: {url}")

    driver = make_driver()

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-condensed.stupid-table"))
        )

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.select_one("table.table-condensed.stupid-table")

        table_rows = table.select("tbody tr") if table else []
        if not table_rows:
            print(" No data rows found in tbody.")
            return

        species_data = []

        for row in table_rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                # There are usually multiple <a> tags: one for map icon, one for species name
                species_links = cols[1].find_all("a", href=True)

                # Filter out the <a> tags that have no visible text other than icon <i>
                def has_visible_text(a_tag):
                    visible_text = ''.join(t for t in a_tag.strings if t.strip() and t.parent.name != 'i').strip()
                    return bool(visible_text)

                species_link = None
                for link in species_links:
                    if has_visible_text(link):
                        species_link = link
                        break  # Found the correct species link with visible name text

                if not species_link:
                    # No valid species link found, skip this row
                    print(f" Skipping row with no visible species name link! Row: {row}")
                    continue

                href = species_link['href']
                species_id = href.split("/")[2]

                sci_name_tag = species_link.find("small")
                if sci_name_tag:
                    sci_name = sci_name_tag.get_text(strip=True)
                    sci_name_tag.extract()
                    common_name = species_link.get_text(strip=True)
                else:
                    sci_name = ""
                    common_name = species_link.get_text(strip=True)

                if not common_name.strip():
                    print(f" Skipping empty common name! Link: {species_link}")
                    continue

                species_name = common_name

                obs_url = f"{BASE_URL}/species/{species_id}/observations/?date_after={start_date}&date_before={end_date}&country_id=20&country_division=25"
                driver.get(obs_url)
                time.sleep(2)

                sub_soup = BeautifulSoup(driver.page_source, 'html.parser')
                obs_rows = sub_soup.select("table.table-bordered.table-striped tbody tr")

                for obs_row in obs_rows:
                    tds = obs_row.find_all("td")
                    if len(tds) >= 3:
                        date_text = tds[0].text.strip()
                        location_tag = tds[2].find("a")
                        location_text = location_tag.get_text(separator=" ", strip=True).replace('\xa0', ' ') if location_tag else "Unknown"
                        species_data.append({
                            "species_name": species_name,
                            "date": date_text,
                            "location": location_text
                        })

        if not species_data:
            print("No observations found.")
            return

        os.makedirs("data", exist_ok=True)
        filename = f"data/observations_{month:02}_{year}.csv"

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "species_name", "location"])
            writer.writeheader()
            for row in species_data:
                writer.writerow(row)

        species_counts = {}
        for s in species_data:
            species_counts[s['species_name']] = species_counts.get(s['species_name'], 0) + 1

        print(f"\n Summary for {month:02}/{year}")
        print(f" Total species (richness): {len(species_counts)}")
        print(f" Total observations: {len(species_data)}\n")
        print(f"{'Species':30} {'# Observations'}")
        for name, count in sorted(species_counts.items(), key=lambda x: -x[1]):
            print(f"{name:30} {count}")

        print(f"\n Data saved to {filename}")

    except Exception as e:
        print(f" Error: {e}")
    finally:
        driver.quit()