import requests
import ssl

url = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt"
filename = "yolov8n.pt"

print(f"Downloading {filename} manually (SSL Verify=False)...")

try:
    response = requests.get(url, verify=False, allow_redirects=True)
    with open(filename, "wb") as f:
        f.write(response.content)
    print("Download Selesai!")
except Exception as e:
    print(f"Download Gagal: {e}")
