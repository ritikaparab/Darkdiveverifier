# backend_verifier.py
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os
import pandas as pd
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Enable CORS

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "normalnew.csv")

# Load the data once when the application starts
try:
    df = pd.read_csv(csv_path)
except FileNotFoundError:
    df = pd.DataFrame()
    print("WARNING: The CSV file 'normalnew.csv' was not found. Please ensure it is in the same directory.")

@app.route('/verify', methods=['POST'])
def verify_credentials():
    """
    Receives credentials via POST request and performs a login attempt.
    """
    data = request.get_json()

    if not all(k in data for k in ('url', 'username', 'password')):
        return jsonify({"status": "Manual Check", "message": "Incomplete data"}), 400

    url = data['url']
    username = data['username']
    password = data['password']

    # --- PROXY CONFIGURATION ---
    proxy_server = os.getenv("PROXY_SERVER", None)
    
    launch_options = {'headless': True}
    if proxy_server:
        launch_options['proxy'] = {'server': proxy_server}
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(**launch_options)
            page = browser.new_page()
            
            page.goto(url, timeout=60000)
            
            # --- INTELLIGENT LOGIN LOGIC ---
            if 'reqres.in' in url:
                username_field = page.locator('input[name="email"]')
                password_field = page.locator('input[name="password"]')
                submit_button = page.locator('button')
            elif 'orangehrmlive.com' in url:
                username_field = page.locator('input[name="username"]')
                password_field = page.locator('input[name="password"]')
                submit_button = page.locator('button[type="submit"]')
            elif 'the-internet.herokuapp.com' in url:
                username_field = page.locator('input[name="username"]')
                password_field = page.locator('input[name="password"]')
                submit_button = page.locator('button[type="submit"]')
            else:
                # Fallback to heuristic-based detection
                username_field = page.locator('input[type="email"], input[name*="user"], input[id*="user"], input[name*="login"], input[id*="login"], input[placeholder*="username"], input[placeholder*="email"], input[placeholder*="user"]').first
                password_field = page.locator('input[type="password"], input[name*="pass"], input[id*="pass"], input[placeholder*="password"]').first
                submit_button = page.locator('button[type="submit"], input[type="submit"], button:has-text("Log In"), button:has-text("Sign in")').first

            if username_field.is_visible() and password_field.is_visible():
                username_field.fill(username)
                password_field.fill(password)
                if submit_button.is_visible():
                    submit_button.click()
                    page.wait_for_timeout(5000)
                else:
                    return jsonify({"status": "Manual Check", "message": "Could not find a submit button."}), 200
            else:
                return jsonify({"status": "Manual Check", "message": "Could not find login fields."}), 200

            # ---- STATUS CLASSIFICATION ----
            if page.locator('text=Log Out').is_visible() or page.locator('text=Welcome').is_visible() or page.locator('p.oxd-userdropdown-name').is_visible() or 'dashboard' in page.url.lower():
                status, message = "Active", "Login successful."
            elif page.locator('text=Invalid credentials').is_visible() or page.locator('text=incorrect password').is_visible() or page.locator('div.orangehrm-login-error').is_visible():
                status, message = "Inactive", "Invalid credentials."
            elif page.locator('text=Two-Factor Authentication').is_visible() or page.locator('input[name="otp"]').is_visible():
                status, message = "Manual Check", "2FA required."
            else:
                status, message = "Manual Check", "Unknown login status."
            
            return jsonify({"status": status, "message": message}), 200

        except Exception as e:
            return jsonify({"status": "Manual Check", "message": str(e)}), 500

@app.route('/get-leaks', methods=['POST'])
def get_leaks():
    """
    Returns filtered leak data based on the provided domain.
    """
    data = request.get_json()
    domain = data.get('domain', '').lower()

    if df.empty:
        return jsonify({"message": "Data file not found on the server."}), 404

    filtered_leaks = df[(df['Url'].str.contains(domain, case=False, na=False)) | 
                        (df['username'].str.contains(domain, case=False, na=False))]
    
    leaks_list = filtered_leaks.to_dict('records')

    return jsonify(leaks_list), 200

if __name__ == '__main__':
    app.run(port=5000, debug=True)
