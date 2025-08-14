import json
import time
import re
import requests
from flask import Flask, render_template_string
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

PRODUCTS_FILE = "products.json"
CONFIG_FILE = "config.json"

# ------------------ Load Config ------------------
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def send_telegram_message(message):
    config = load_config()
    token = config.get("telegram_bot_token")
    chat_id = config.get("telegram_chat_id")

    if not token or not chat_id:
        print("Telegram config missing")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram error:", e)

# ------------------ Load and Save ------------------
def load_products():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=4)

# ------------------ Selenium Setup ------------------
def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

# ------------------ Price Fetch ------------------
def fetch_price_samsung_in(url):
    driver = init_driver()
    price_value = None
    try:
        driver.get(url)

        # Wait for the correct element
        price_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".s-rdo-price")  # Samsung India price class
            )
        )

        price_text = price_element.text.strip()
        # Extract only the last ₹xxxxx.xx part
        match = re.search(r"₹[\d,]+(?:\.\d{1,2})?", price_text)
        if match:
            price_clean = match.group().replace("₹", "").replace(",", "")
            # Convert to integer (remove .00 if exists)
            price_value = int(float(price_clean))

    except Exception as e:
        print("Price fetch error:", e)
    finally:
        driver.quit()

    return price_value

# ------------------ Tracker Logic ------------------
def check_prices():
    products = load_products()
    for product in products:
        if not product.get("enabled", True):
            continue

        print(f"Checking price for {product['name']}...")
        current_price = fetch_price_samsung_in(product["url"])
        if current_price:
            product["current_price"] = current_price
            if current_price <= product["target_price"]:
                product["status"] = "✅ Target reached!"
                send_telegram_message(f"🎯 {product['name']} now at ₹{current_price} (Target ₹{product['target_price']})\n{product['url']}")
            else:
                product["status"] = "💲 Above target"
        else:
            product["current_price"] = None
            product["status"] = "❌ Price not found"

    save_products(products)

# ------------------ Flask Web UI ------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Samsung Price Tracker</title>
    <style>
        body { font-family: Arial; margin: 40px; }
        table { border-collapse: collapse; width: 80%; }
        th, td { border: 1px solid #ddd; padding: 8px; }
        th { background: #333; color: #fff; }
        tr:nth-child(even) { background: #f2f2f2; }
    </style>
</head>
<body>
<h1>Samsung Price Tracker</h1>
<table>
<tr>
    <th>Product</th>
    <th>Target Price</th>
    <th>Current Price</th>
    <th>Status</th>
</tr>
{% for p in products %}
<tr>
    <td><a href="{{ p.url }}" target="_blank">{{ p.name }}</a></td>
    <td>₹{{ p.target_price }}</td>
    <td>{% if p.current_price %}₹{{ p.current_price }}{% else %}-{% endif %}</td>
    <td>{{ p.status }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

@app.route("/")
def index():
    check_prices()
    products = load_products()
    return render_template_string(HTML_TEMPLATE, products=products)

if __name__ == "__main__":
    while True:
        check_prices()
        time.sleep(3600)  # check every 1 hour
