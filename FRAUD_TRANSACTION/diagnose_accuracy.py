import os

def scan_file_metadata(path):
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192).decode('utf-8', errors='ignore').lower()
            forgery_markers = [
                'photoshop', 'adobe imageready', 'canva', 'gimp', 'picsart', 
                'screenshot', 'screen capture', 'snipping tool', 'lightshot',
                'iphone', 'android', 'pixel', 'samsung', 'camera', 'creator',
                'gpay', 'paytm', 'phonepe', 'bhim', 'upi_capture', 'whatsapp'
            ]
            for marker in forgery_markers:
                if marker in chunk:
                    return True, f"METADATA: Found {marker.upper()} signature."
            return False, "METADATA: Clean."
    except Exception as e:
        return False, f"ERROR: {str(e)}"

def run_diagnostics():
    upload_dir = r"c:\Users\KRISHNA PARVATHI\Downloads\FRAUD_TRANSACTION (1)\FRAUD_TRANSACTION\web 1\static\uploads"
    files = os.listdir(upload_dir)
    print(f"\n[DIAGNOSTICS] Scanning {len(files)} uploaded files...\n" + "-"*60)
    
    for filename in files:
        path = os.path.join(upload_dir, filename)
        is_manipulated, detail = scan_file_metadata(path)
        
        # Filename check
        fraud_indicators = ['fraud', 'suspicious', 'alert', 'blackmoney', 'illegal']
        filename_match = any(ind in filename.lower() for ind in fraud_indicators) or filename.lower().startswith('screenshot')
        
        status = "FRAUD" if (is_manipulated or filename_match) else "GENUINE"
        print(f"FILE: {filename[:40]:<40} | RESULT: {status:<8} | {detail}")

if __name__ == "__main__":
    run_diagnostics()
