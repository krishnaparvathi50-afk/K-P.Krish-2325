import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_fraud_detection():
    session = requests.Session()
    
    # 1. Register
    print("Registering user...")
    reg_data = {
        'username': 'testuser999',
        'email': 'test999@example.com',
        'mobile': '+919999999999',
        'password': 'password123',
        'confirm_password': 'password123'
    }
    r = session.post(f"{BASE_URL}/register", data=reg_data)
    if r.status_code != 200:
        print(f"Registration failed: {r.status_code}")
        return

    # 2. Login
    print("Logging in...")
    login_data = {
        'username': 'testuser999',
        'password': 'password123'
    }
    r = session.post(f"{BASE_URL}/login", data=login_data)
    if r.status_code != 200:
        print(f"Login failed: {r.status_code}")
        return

    # 3. Upload a 'fraud' file
    print("Uploading fraudulent statement...")
    # Create a dummy file
    files = {'file': ('suspicious_statement.png', b'dummy content', 'image/png')}
    r = session.post(f"{BASE_URL}/upload_statement", files=files)
    
    if "FRAUD DETECTED" in r.text:
        print("SUCCESS: Fraud detection triggered correctly!")
        if "result-card fraud" in r.text:
            print("SUCCESS: UI correctly identifies it with 'fraud' class.")
    else:
        print("FAILURE: Fraud was not detected.")
        print(r.text[:500])

if __name__ == "__main__":
    try:
        test_fraud_detection()
    except Exception as e:
        print(f"Error: {e}")
