# backend_verifier.py
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import requests
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # This line was added to enable CORS

# Example Captcha solving API key (replace with real one, e.g. 2Captcha)
CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "YOUR_2CAPTCHA_KEY")

def solve_captcha(site_key, url):
    """
    Solve CAPTCHA using 2Captcha API.
    """
    try:
        # Send task
        captcha_req = requests.post(
            "http://2captcha.com/in.php",
            data={
                "key": CAPTCHA_API_KEY,
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": url,
                "json": 1
            }
        ).json()

        if captcha_req.get("status") != 1:
            return None

        captcha_id = captcha_req["request"]

        # Poll for result
        for _ in range(20):  # retry ~40s
            res = requests.get(
                f"http://2captcha.com/res.php?key={CAPTCHA_API_KEY}&action=get&id={captcha_id}&json=1"
            ).json()
            if res.get("status") == 1:
                return res["request"]
        return None
    except Exception as e:
        return None


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

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)

            # Fill login form (selectors must match actual site)
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3000)

            # ---- STATUS CLASSIFICATION ----
            if page.locator('text=Log Out').is_visible():
                status, message = "Active", "Login successful."

            elif page.locator('text=Invalid credentials').is_visible() or page.locator('text=incorrect password').is_visible():
                status, message = "Inactive", "Invalid credentials."

            elif page.locator('text=reCAPTCHA').is_visible() or page.locator('iframe[src*="recaptcha"]').is_visible():
                # Handle CAPTCHA
                site_key = page.get_attribute('iframe[src*="recaptcha"]', "src").split("k=")[1].split("&")[0]
                token = solve_captcha(site_key, url)
                if token:
                    page.evaluate("""token => {
                        document.querySelector('textarea[name="g-recaptcha-response"]').value = token;
                    }""", token)
                    page.click('button[type="submit"]')
                    page.wait_for_timeout(3000)

                    if page.locator('text=Log Out').is_visible():
                        status, message = "Active", "Login successful (with captcha)."
                    else:
                        status, message = "Manual Check", "Captcha solved, but login unclear."
                else:
                    status, message = "Manual Check", "Captcha could not be solved."

            elif page.locator('text=Two-Factor Authentication').is_visible() or page.locator('input[name="otp"]').is_visible():
                status, message = "Manual Check", "2FA required."

            else:
                status, message = "Manual Check", "Unknown login status."

            browser.close()
            return jsonify({"status": status, "message": message}), 200

        except Exception as e:
            return jsonify({"status": "Manual Check", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(port=5000, debug=True)
