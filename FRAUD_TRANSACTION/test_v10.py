import requests
import os

BASE_URL = "http://127.0.0.1:5000"
USER = "v10_user"
PASS = "v10_pass"

def run_v10_test():
    session = requests.Session()
    print(f"\n[DEMO] BALANCED ANALYSIS TEST (v10)\n{'-'*50}")

    # 1. Register & Login
    session.post(f"{BASE_URL}/register", data={"username": USER, "email": "v10@test.com", "mobile": "+919629450010", "password": PASS, "confirm_password": PASS})
    session.post(f"{BASE_URL}/login", data={"username": USER, "password": PASS})

    # 2. Files to test
    tests = [
        ("normal_screenshot.png", b"\x89PNG\r\n\x1a\n! [SCREENSHOT_DATA]\nEverything looks normal.", "image/png", "GENUINE"),
        ("urgent_fraud.png", b"\x89PNG\r\n\x1a\n! [SCREENSHOT_DATA]\nURGENT TRANSFER detected.", "image/png", "FRAUD"),
        ("photoshop_forgery.jpg", b"GIF89a\x00\n[PHOTOSHOP_MARKER]\nEdited file.", "image/jpeg", "FRAUD")
    ]

    for filename, content, mimetype, expected in tests:
        with open(filename, "wb") as f: f.write(content)
        
        print(f"[TEST] Scanning: {filename} (Expected: {expected})")
        try:
            with open(filename, "rb") as f:
                r = session.post(f"{BASE_URL}/upload_statement", files={"file": (filename, f, mimetype)})
                
                if f"Result: {expected}" in r.text:
                    print(f"[{filename}] DETECTION: SUCCESS (Result: {expected})")
                    if "Reason:" in r.text:
                        start = r.text.find("Reason:")
                        end = r.text.find("</p>", start)
                        print(f"       {r.text[start:end]}")
                else:
                    print(f"[{filename}] DETECTION: FAILED (Result mismatch)")
                print(f"{'-'*50}")
        except Exception as e:
            print(f"[ERROR] {str(e)}")

if __name__ == "__main__":
    run_v10_test()
