import json
import time
from flask import Flask, render_template_string
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

app = Flask(__name__)

PRODUCTS_FILE = "products.json"

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
    return webdriver.Chrome(options=chrome_options)

# ------------------ Price Fetch ------------------
def fetch_price_samsung_in(url):
    driver = init_driver()
    try:
        driver.get(url)

        # Wait up to 15s for price to appear — try exact span.s-rdo-price first
        try:
            price_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "span.s-rdo-price")
                )
            )
        except:
            # Fallback to older selectors if s-rdo-price not found
            price_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".product-details__price, .pd-price, .price")
                )
            )

        price_text = price_element.text.strip()

        # If EMI format is present: "₹10888.78/mo. or ₹97999.00"
        if "or" in price_text:
            price_text = price_text.split("or")[-1].strip()

        # Clean ₹ and commas
        price_text = price_text.replace("₹", "").replace(",", "").strip()

        # Extract number
        if price_text.isdigit():
            return int(price_text)
        else:
            numbers = re.findall(r"\d+", price_text)
            if numbers:
                return int("".join(numbers))

    except Exception as e:
        print("Price fetch error:", e)
        return None
    finally:
        driver.quit()

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
    app.run(host="0.0.0.0", port=5000)
