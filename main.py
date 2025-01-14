from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import sqlite3
import time

def remove_event_elements(driver):
    script = """
        const eventList = document.querySelectorAll('#explore_tabpanel-0 div ul li');
        eventList.forEach(event => event.remove());
    """
    driver.execute_script(script)

# Function to update or add the query parameter
def update_query_param(url, key, value):
    url_parts = urlparse(url)
    query_params = parse_qs(url_parts.query)

    # Update or add the key-value pair
    query_params[key] = [value]

    # Rebuild the URL with the updated query parameters
    updated_query = urlencode(query_params, doseq=True)
    updated_url_parts = url_parts._replace(query=updated_query)
    return urlunparse(updated_url_parts)

# Set up Selenium WebDriver with Chrome
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--lang=en")

service = Service()  # Update with the path to your ChromeDriver

driver = webdriver.Chrome(service=service, options=chrome_options)

# Database setup
conn = sqlite3.connect('events.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS events (
    event_link TEXT PRIMARY KEY,
    event_title TEXT,
    event_date TEXT,
    event_time TEXT,
    event_location TEXT,
    state TEXT,
    city TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (
    ticket_name TEXT,
    ticket_price REAL,
    event_link TEXT,
    FOREIGN KEY (event_link) REFERENCES events (event_link)
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS scraped_cities (
    city TEXT PRIMARY KEY,
    state TEXT
)''')

# Base URL
url = "https://www.viagogo.com/United-States"

# Navigate to the URL
driver.get(url)

# XPath for state links
state_xpath = '//*[@id="app"]/div[4]/div[2]/div[1]/div/ul//li//a'

# Extract state links
# Extract state links
state_links = driver.find_elements(By.XPATH, state_xpath)
state_hrefs = []  # Collect all state links first
for state_link in state_links:
    state_href = state_link.get_attribute('href')
    if state_href and state_href != "https://www.viagogo.com/":
        state_hrefs.append(state_href)
        print("State Link:", state_href)

# Visit each state link to collect city links
for state_href in state_hrefs:
    driver.get(state_href)

    # Extract state from state_href (assumes URL structure includes state)
    state = state_href.split('/')[3]

    # XPath for city links on the state page
    city_xpath = '//*[@id="app"]/div[4]/div[2]//ul//li//a'
    city_links = driver.find_elements(By.XPATH, city_xpath)

    # Start processing each city
    for i in range(len(city_links)):
        try:
            # Re-fetch city links and get the current city
            city_links = driver.find_elements(By.XPATH, city_xpath)
            city_link = city_links[i]
            city_href = city_link.get_attribute('href')
            if not city_href:
                continue

            # Extract city name from the URL
            city = city_href.split('/')[-1]

            # Skip cities that are already scraped
            cursor.execute('SELECT 1 FROM scraped_cities WHERE city = ? AND state = ?', (city, state))
            if cursor.fetchone():
                print(f"City {city} in state {state} already scraped. Skipping.")
                continue

            print("Processing City:", city_href)

            # Navigate to the city page
            driver.get(city_href)

            # Keep clicking "Load More" and process events until no new events are loaded
            while True:
                # Extract event details
                event_container_xpath = '//*[@id="explore_tabpanel-0"]/div/div[2]/ul/li'
                try:
                    event_containers = driver.find_elements(By.XPATH, event_container_xpath)
                    if not event_containers:
                        print("No more events to process.")
                        break

                    for event in event_containers:
                        try:
                            # Extract event details
                            event_link = event.find_element(By.XPATH, './/a').get_attribute('href')
                            event_link = update_query_param(event_link, "quantity", "1")

                            event_title = event.find_element(By.XPATH, './/a//p[1]').text
                            event_date_time = event.find_element(By.XPATH, './/a//p[2]').text
                            event_location = event.find_element(By.XPATH, './/a//p[1]').text
                            event_date, event_time = event_date_time.split(' • ') if ' • ' in event_date_time else (event_date_time, '')

                            print("Event Link:", event_link)
                            print("Event Title:", event_title)

                            # Save event to the database
                            try:
                                cursor.execute('''INSERT INTO events (event_link, event_title, event_date, event_time, event_location, state, city)
                                                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                            (event_link, event_title, event_date, event_time, event_location, state, city))
                                conn.commit()
                            except sqlite3.IntegrityError:
                                print("Duplicate event, skipping:", event_link)

                        except Exception as e:
                            print("Error processing event:", e)

                    # Remove processed event elements using JavaScript
                    remove_event_elements(driver)

                    # Click "Load More" button
                    load_more_xpath = '//*[@id="explore_tabpanel-0"]/div/div[2]/div/div/button'
                    load_more_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, load_more_xpath))
                    )
                    load_more_button.click()
                    time.sleep(5)

                except Exception as e:
                    print("No more events or button not clickable:", e)
                    break

            # Mark city as scraped
            cursor.execute('INSERT INTO scraped_cities (city, state) VALUES (?, ?)', (city, state))
            conn.commit()

        except Exception as e:
            print("Error processing city:", e)

# Check if all cities have been scraped
cursor.execute('SELECT COUNT(*) FROM scraped_cities')
scraped_city_count = cursor.fetchone()[0]

if scraped_city_count > 0:
    print(f"All cities have been scraped. Clearing the scraped_cities table.")
    cursor.execute('DELETE FROM scraped_cities')
    conn.commit()

driver.quit()
conn.close()


driver.quit()
conn.close()
