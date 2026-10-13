from setuptools import setup, find_packages

setup(
    name="natuurspotter",
    version="0.1.0",
    author="Mazan Ali",
    description="Collect, map and report reptile and amphibian observations in Walloon Brabant (Belgium)",
    license="MIT",
    packages=find_packages(include=["Natuurspotter", "Natuurspotter.*"]),
    python_requires=">=3.8",
    install_requires=[
        "requests",
        "beautifulsoup4",
        "selenium",
        "webdriver-manager",
        "wikipedia",
        "folium",
        "fpdf",
        "Pillow",
        "matplotlib",
        "openai>=1.0",
        "python-dotenv",
    ],
)
