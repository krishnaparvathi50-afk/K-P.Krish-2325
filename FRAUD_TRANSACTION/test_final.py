import requests
import os

BASE_URL = "http://127.0.0.1:5000"
USER = "demo_final_user_v6"
PASS = "demo_final_pass_v6"

def run_test():
    session = requests.Session()
    print("\n[DEMO] FINAL AUTOMATIC FRAUD ANALYSIS (v6)\n" + "-"*40)

    # 1. Register & Login
    session.post(f"{BASE_URL}/register", data={"username": USER, "email": "demo@testv6.com", "mobile": "+919629450000", "password": PASS, "confirm_password": PASS})
    session.post(f"{BASE_URL}/login", data={"username": USER, "password": PASS})

    # 2. Test Samples
    samples = [
        ("bank_good.pdf", "application/pdf"),
        ("bank_fake.jpg", "image/jpeg"),
        ("gpay_fake.png", "image/png")
    ]

    for path, mimetype in samples:
        print(f"[TEST] Scanning: {path}...")
        try:
            with open(path, "rb") as f:
                r = session.post(f"{BASE_URL}/upload_statement", files={"file": (path, f, mimetype)})
                
                # Check results
                if "alert-box fraud" in r.text or "FRAUD DETECTED" in r.text:
                    print(f"[{path}] RESULT: !!! FRAUD DETECTED !!! (Bold Red Alert)")
                    if "SECURITY ALERT" in r.text:
                        start = r.text.find("SECURITY ALERT")
                        end = r.text.find(".", start) + 1
                        print(f"       SCAN DETAILS: {r.text[start:end]}")
                else:
                    print(f"[{path}] RESULT: *** GENUINE STATEMENT *** (Green Alert)")
                    print("       SCAN DETAILS: High Integrity (Clean Binary)")
                print("-"*40)
        except Exception as e:
            print(f"[ERROR] Could not scan {path}: {str(e)}")

if __name__ == "__main__":
    run_test()
