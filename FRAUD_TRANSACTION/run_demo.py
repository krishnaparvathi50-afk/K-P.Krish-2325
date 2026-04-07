import requests
import os

# --- DEMO CONFIGURATION ---
BASE_URL = "http://127.0.0.1:5000"
USER = "demo_user_123"
PASS = "demo_pass_123"

def run_demo():
    session = requests.Session()
    print(f"\n[DEMO] STARTING AUTOMATIC FRAUD ANALYSIS DEMO (v6)\n{'-'*50}")

    # 1. Register User
    print(f"[1] Registering demo user '{USER}'...")
    reg_data = {
        "username": USER,
        "email": "demo@example.com",
        "mobile": "+919629451234",
        "password": PASS,
        "confirm_password": PASS
    }
    r = session.post(f"{BASE_URL}/register", data=reg_data)
    
    # 2. Login
    print(f"[2] Logging in...")
    r = session.post(f"{BASE_URL}/login", data={"username": USER, "password": PASS})
    
    if "dashboard" in r.url or r.status_code == 200:
        print("[SUCCESS] Logged in successfully.\n")
    else:
        print("[ERROR] Login failed. Is the server running?")
        return

    # 3. Test Samples
    samples = [
        ("Official_Bank_Statement.pdf", "application/pdf"),
        ("Statement_April_Official.jpg", "image/jpeg"),
        ("Digital_Payment_Receipt.png", "image/png")
    ]

    for filename, mimetype in samples:
        print(f"[TEST] Scanning: {filename}...")
        try:
            with open(filename, "rb") as f:
                files = {"file": (filename, f, mimetype)}
                r = session.post(f"{BASE_URL}/upload_statement", files=files)
                
                # Check for Result UI components
                if "alert-box fraud" in r.text or "FRAUD DETECTED" in r.text:
                    print(f"[{filename}] DETECTION: !!! FRAUD !!! (Bold Red Alert)")
                else:
                    print(f"[{filename}] DETECTION: *** SAFE *** (Green Alert)")
                    
                # Look for the internal analysis details in the flash message
                if "SECURITY ALERT" in r.text:
                    start = r.text.find("SECURITY ALERT")
                    end = r.text.find(".)", start) + 2
                    if end < start: end = r.text.find("!", start) + 1
                    print(f"       SCAN DETAILS: {r.text[start:end]}")
                print(f"{'-'*50}")
        except FileNotFoundError:
            print(f"[ERROR] Sample {filename} not found.")

if __name__ == "__main__":
    run_demo()
