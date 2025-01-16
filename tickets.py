from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException
)
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import sqlite3
import time
import hashlib

def update_query_param(url, key, value):
    print(f"[DEBUG] Updating query parameter '{key}' to '{value}' in URL: {url}")
    url_parts = urlparse(url)
    query_params = parse_qs(url_parts.query)
    query_params[key] = [str(value)]
    updated_query = urlencode(query_params, doseq=True)
    updated_url_parts = url_parts._replace(query=updated_query)
    new_url = urlunparse(updated_url_parts)
    print(f"[DEBUG] Updated URL: {new_url}")
    return new_url

print("[DEBUG] Setting up Selenium WebDriver.")
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--lang=en")
service = Service()

driver = webdriver.Chrome(service=service, options=chrome_options)
print("[DEBUG] Selenium WebDriver initialized.")

print("[DEBUG] Connecting to SQLite database 'events.db'.")
conn = sqlite3.connect('events.db')
cursor = conn.cursor()

# [MODIFICATION] Drop the existing tickets table if it exists
cursor.execute("DROP TABLE IF EXISTS tickets")

# [MODIFICATION] Ensure tickets table has event_location, zone, and is_vip columns
print("[DEBUG] Ensuring tickets table exists with required schema including event_location, zone, and is_vip.")
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        ticket_name TEXT,
        ticket_price REAL,
        event_link TEXT,
        quantity INTEGER,
        unique_id TEXT UNIQUE,
        event_location TEXT,
        zone TEXT,
        is_vip INTEGER,  -- 1 for VIP, 0 for Non-VIP
        FOREIGN KEY (event_link) REFERENCES events (event_link)
    )
''')

no_tickets_xpath = '//*[@id="stubhub-event-detail-listings-grid"]/div[1]/div/div/div[2]/span'
event_location_xpath = '//*[@id="event-detail-header"]/div/div/div[1]/div[2]/div/div/div[2]/button'
ticket_container_xpath = '//*[@id="listings-container"]/div | /html/body/div[1]/div[2]/div[3]/div/div[2]/div/div[3]/div[*]'
ticket_name_xpath = './div/div[2]/div/div[1]/div[1]/div[1] | ./div/div/div[1]/div[1]/div[1]'
ticket_price_xpath = './div/div[2]/div/div[1]/div[2]/div[1]/div[2] | ./div/div/div/div[2]/div/div[2] | .//*[contains(text(), "$")]'

# [MODIFICATION] XPath for the dialog's zone element and close button
zone_xpath = '//*[@id="selected-buyer-listing"]/div[2]/div[1]/div/div[2]/div[1]/div[2]/div[2]'
# XPath for VIP status within the modal
vip_status_xpath = '//*[@id="selected-buyer-listing"]/div[2]/div[5]/div/div[2]/div/p'
# Updated XPath to target the SVG parent instead of the path
close_dialog_xpath = '//*[@id="modal-root"]/div/div/div'

max_quantity = 5
print(f"[DEBUG] max_quantity set to {max_quantity}")

print("[DEBUG] Retrieving all events from the 'events' table.")
cursor.execute('SELECT event_link FROM events')
events = cursor.fetchall()
print(f"[DEBUG] Found {len(events)} event(s) in the database.")

for event in events:
    event_link = event[0]
    print(f"\n[DEBUG] Processing event: {event_link}")

    quantity = 1
    any_tickets_found = False
    event_location = ""

    # Fetch the event location once outside the main loop
    try:
        print("[DEBUG] Attempting to open event page to get location.")
        driver.get(event_link)
        event_location = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, event_location_xpath))
        ).text
        print(f"[DEBUG] Event location found once for this event: {event_location}")
    except (NoSuchElementException, TimeoutException):
        event_location = ""
        print("[DEBUG] Event location not found or timed out, proceeding with empty location.")

    while True:
        print(f"[DEBUG] Starting loop with quantity={quantity} for event: {event_link}")

        if quantity > max_quantity:
            print(f"[DEBUG] Reached max quantity {max_quantity} for {event_link}. Stopping.")
            break

        current_url = update_query_param(event_link, "quantity", quantity)
        print(f"[DEBUG] Navigating to: {current_url}")
        driver.get("https://www.viagogo.com/Colorado-Mammoth-Parking-Passes/Colorado-Mammoth-Tickets/E-155401221?quantity=1")

        # Check if "no tickets available" element is present
        try:
            print("[DEBUG] Checking for 'no tickets available' element.")
            no_tickets_element = driver.find_element(By.XPATH, no_tickets_xpath)
            if no_tickets_element:
                print(f"[DEBUG] No tickets found at quantity {quantity}")
                if not any_tickets_found and quantity > 20:
                    print("[DEBUG] No tickets found for any quantity after 20 attempts, moving to next event.")
                    break
                quantity += 1
                continue
        except NoSuchElementException:
            print("[DEBUG] 'No tickets' element not found, continuing.")

        print("[DEBUG] Waiting 2 seconds for the page to load ticket containers.")
        time.sleep(2)

        print("[DEBUG] Finding ticket containers.")
        ticket_containers = driver.find_elements(By.XPATH, ticket_container_xpath)
        print(f"[DEBUG] Found {len(ticket_containers)} ticket container(s) at quantity={quantity}.")

        if not ticket_containers:
            if not any_tickets_found and quantity > 20:
                print("[DEBUG] No tickets found for any quantity after 20 attempts, moving to next event.")
                break
            print("[DEBUG] No ticket containers found, incrementing quantity.")
            quantity += 1
            continue

        any_tickets_found = True
        processed_tickets = set()
        print("[DEBUG] Processing containers until none remain...")

        while True:
            print("[DEBUG] Re-checking for containers.")
            ticket_containers = driver.find_elements(By.XPATH, ticket_container_xpath)
            if not ticket_containers:
                print("[DEBUG] No more containers found, breaking inner loop.")
                break

            for index, container in enumerate(ticket_containers, start=1):
                print(f"[DEBUG] Processing container #{index}.")
                try:
                    container_text = container.text
                    if "sold" in container_text.lower():
                        print("[DEBUG] 'sold' detected in container text, removing this container and skipping.")
                        driver.execute_script("arguments[0].remove();", container)
                        time.sleep(0.5)
                        continue

                    print("[DEBUG] Attempting to find ticket_name element.")
                    ticket_name_element = container.find_element(By.XPATH, ticket_name_xpath)
                    raw_ticket_name = ticket_name_element.text.strip()
                    print(f"[DEBUG] Extracted raw_ticket_name: {raw_ticket_name}")

                    # Insert newlines to make the ticket_name more readable
                    ticket_name = raw_ticket_name.replace("Section ", "Section\n")
                    ticket_name = ticket_name.replace("Row ", "Row\n")
                    ticket_name = ticket_name.replace("ticket", "ticket\n")
                    ticket_name = ticket_name.strip()

                    print(f"[DEBUG] ticket_name after inserting newlines:\n{ticket_name}")

                    print("[DEBUG] Attempting to find ticket_price element.")
                    while True:
                        try:
                            ticket_price_element = container.find_element(By.XPATH, ticket_price_xpath)
                            break
                        except NoSuchElementException:
                            pass
                    ticket_price = ticket_price_element.text.strip()
                    print(f"[DEBUG] Extracted ticket_price: {ticket_price}")

                    # [MODIFICATION] Click the container using Selenium's native click to reveal dialog
                    try:
                        print("[DEBUG] Attempting to click the container to reveal zone and VIP information.")
                        container.click()  # Native Selenium click
                        print("[DEBUG] Container clicked successfully.")
                    except (ElementClickInterceptedException, ElementNotInteractableException) as e:
                        print(f"[DEBUG] Could not click the container: {e}")
                        continue  # Skip to next container if click fails

                    # [MODIFICATION] Extract the 'zone' from the dialog
                    try:
                        print("[DEBUG] Waiting for zone element in the dialog to be present.")
                        zone_element = WebDriverWait(driver, 10).until(
                            EC.visibility_of_element_located((By.XPATH, zone_xpath))
                        )
                        zone = zone_element.text.strip()
                        print(f"[DEBUG] Extracted zone: {zone}")
                    except (NoSuchElementException, TimeoutException):
                        zone = ""
                        print("[DEBUG] Zone element not found or timed out, proceeding with empty zone.")

                    # [MODIFICATION] Extract VIP status from the dialog using provided XPath
                    try:
                        print("[DEBUG] Attempting to extract VIP status using provided XPath.")
                        vip_element = driver.find_element(By.XPATH, vip_status_xpath)
                        vip_text = vip_element.text.strip().lower()
                        is_vip = 1 if 'vip' in vip_text else 0
                        print(f"[DEBUG] Extracted VIP status: {'VIP' if is_vip else 'Non-VIP'}")
                    except (NoSuchElementException, TimeoutException):
                        is_vip = 0  # Default to Non-VIP if not found
                        print("[DEBUG] VIP status element not found or timed out, defaulting to Non-VIP.")

                    # [MODIFICATION] Close the dialog by clicking the "X" button
                    try:
                        print("[DEBUG] Attempting to close the dialog by clicking the 'X' button.")
                        close_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, close_dialog_xpath)))
                        close_button.click()
                        print("[DEBUG] Dialog closed successfully.")
                    except (NoSuchElementException, TimeoutException, ElementClickInterceptedException, ElementNotInteractableException) as e:
                        print(f"[DEBUG] Could not close the dialog: {e}")

                    unique_str = f"{event_link}-{raw_ticket_name}-{ticket_price}-{quantity}-{index}"
                    print(f"[DEBUG] Generated unique_str: {unique_str}")
                    unique_id = hashlib.sha256(unique_str.encode('utf-8')).hexdigest()
                    print(f"[DEBUG] Generated unique_id: {unique_id}")

                    if unique_id in processed_tickets:
                        print(f"[DEBUG] Duplicate detected in this run, skipping: {ticket_name}, {ticket_price}, {quantity}, Index: {index}")
                    else:
                        print("[DEBUG] Attempting to insert ticket into database with event location, zone, and VIP status.")
                        try:
                            cursor.execute('''INSERT INTO tickets (ticket_name, ticket_price, event_link, quantity, unique_id, event_location, zone, is_vip)
                                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                           (ticket_name, ticket_price, current_url, quantity, unique_id, event_location, zone, is_vip))
                            conn.commit()
                            processed_tickets.add(unique_id)
                            print("[DEBUG] Ticket inserted successfully.")
                        except sqlite3.IntegrityError:
                            print(f"[DEBUG] Duplicate ticket skipped by DB constraint: {ticket_name}, {ticket_price}, {quantity}, Index: {index}")

                except Exception as e:
                    print(f"[DEBUG] Error extracting ticket info: {e}")

                print("[DEBUG] Removing processed container from the DOM.")
                try:
                    driver.execute_script("arguments[0].remove();", container)
                except StaleElementReferenceException:
                    pass
                time.sleep(0.5)

        print(f"[DEBUG] Finished processing all containers for quantity={quantity}, incrementing quantity.")
        quantity += 1

print("[DEBUG] All events processed. Closing browser and database connection.")
driver.quit()
conn.close()
print("[DEBUG] Script execution completed.")
