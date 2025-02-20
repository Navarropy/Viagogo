# Viagogo Event Scraper

This Python script scrapes event data from Viagogo and stores it in a SQLite database.

## Requirements

- Python 3.6 or higher
- Selenium
- ChromeDriver (download and place it in your PATH or specify the path in the script)
- SQLite3

## Installation

1.  **Install the required Python packages:**
    ```bash
    pip install selenium
    ```
2.  **Download ChromeDriver:**
    - Download the appropriate ChromeDriver version for your Chrome browser from [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads)
    - Extract the downloaded file and place the `chromedriver` executable in your system's PATH or specify the path in the script.
3.  **Install SQLite3:**
    - SQLite3 is typically included with Python installations.

## Usage

1.  **Update the `service = Service()` line in the script to specify the path to your ChromeDriver if it's not in your PATH.**
2.  **Run the script:**
    ```bash
    python viagogo_scraper.py
    ```
    - The script will navigate to Viagogo, extract state links, and then proceed to scrape city links within each state.
    - It will extract event details (link, title, date, time, location) and ticket information (name, price).
    - The data will be stored in an SQLite database named `events.db`.
    - The script includes logic to handle pagination by clicking the "Load More" button and to avoid scraping duplicate events.

## Database Structure

The script creates three tables in the `events.db` database:

-   **events:** Stores event information.
-   **tickets:** Stores ticket information for each event.
-   **scraped\_cities:** Keeps track of scraped cities to avoid redundant scraping.

## Notes

-   The script uses XPath to locate elements on the Viagogo website. Any changes to the website structure may require updating the XPaths in the code.
-   The script uses a headless Chrome browser (optional) to avoid opening a visible browser window. You can disable headless mode by commenting out the `chrome_options.add_argument("--headless")` line.
-   The script includes error handling and logging to assist in debugging.
-   The script is designed for educational purposes and personal use. Respect Viagogo's terms of service and use the script responsibly.

## Disclaimer

This script is provided as-is without warranty of any kind. The authors are not responsible for any consequences arising from the use of this script. Please use it responsibly and ethically.
