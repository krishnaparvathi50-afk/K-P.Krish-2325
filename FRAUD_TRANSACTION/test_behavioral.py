import requests
import os

BASE_URL = "http://127.0.0.1:5000"
USER = "behavioral_user"
PASS = "behavioral_pass"

def run_behavioral_test():
    # 1. Create a file with the suspicious keywords
    filename = "behavioral_fraud_test.jpg"
    with open(filename, "wb") as f:
        f.write(b"GIF89a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00! \n[SECURITY_NOTICE]\nURGENT TRANSFER TO UNKNOWN ACCOUNT detected.\nCASH DEPOSIT ANOMALY identified in pattern.")

    session = requests.Session()
    print(f"\n[DEMO] BEHAVIORAL ANALYSIS TEST (v9)\n{'-'*50}")

    # 2. Register & Login
    session.post(f"{BASE_URL}/register", data={"username": USER, "email": "v9@test.com", "mobile": "+919629459000", "password": PASS, "confirm_password": PASS})
    session.post(f"{BASE_URL}/login", data={"username": USER, "password": PASS})

    # 3. Upload & Verify
    print(f"[TEST] Scanning: {filename} (Contains 'Urgent Transfer' & 'Anomaly')")
    try:
        with open(filename, "rb") as f:
            r = session.post(f"{BASE_URL}/upload_statement", files={"file": (filename, f, "image/jpeg")})
            
            # Check for the specific Result/Reason format
            if "Result: FRAUD" in r.text or "Result: FRAUD" in r.text:
                print(f"[{filename}] DETECTION: !!! Result: FRAUD !!!")
                if "Reason:" in r.text:
                    start = r.text.find("Reason:")
                    end = r.text.find("</p>", start)
                    print(f"       {r.text[start:end]}")
            else:
                print(f"[{filename}] DETECTION: FAILED (Expected FRAUD)")
            
            print(f"{'-'*50}")
    except Exception as e:
        print(f"[ERROR] {str(e)}")

if __name__ == "__main__":
    run_behavioral_test()
