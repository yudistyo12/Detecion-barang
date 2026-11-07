import cv2
import numpy as np
import time
import os
import pygame
from gtts import gTTS
from ultralytics import YOLO
import ssl
import winsound

# BYPASS SSL ERROR
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

class SecuritySystem:
    def __init__(self, source=0):
        # --- KONFIGURASI WARNA ---
        self.COLOR_SAFE = (0, 255, 0)
        self.COLOR_THIEF = (255, 0, 0)     # Biru (Person)
        self.COLOR_ITEM_MISSING = (0, 0, 255) # Merah (Stolen)

        # --- KONFIGURASI FILE ---
        self.THIEF_ALERT_FILE = "alert_thief.mp3"
        self.STOLEN_ALERT_FILE = "alert_stolen.mp3"
        self.THIEF_TEXT = "Awas, ada pencuri masuk!"
        self.STOLEN_TEXT = "Barang telah dicuri!"
        self.LANG = 'id'

        # --- PARAMETER ---
        self.BACKGROUND_THRESHOLD = 4000
        self.COOLDOWN_SECONDS = 4
        self.last_alert_time = 0
        self.last_motion_time = 0

        # Init Model & Audio
        self.init_audio()
        print("Loading AI Model (YOLOv8)...")
        self.model = YOLO("yolov8n.pt")
        
        # Init Camera
        print(f"Membuka kamera: {source}")
        self.cap = cv2.VideoCapture(source)
        
        # JANGAN SET RESOLUSI JIKA IP CAMERA (Bisa error/lag)
        if isinstance(source, int): 
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def init_audio(self):
        print("Inisialisasi Audio...")
        try:
            pygame.mixer.init()
        except: pass

        if not os.path.exists(self.THIEF_ALERT_FILE) or os.path.getsize(self.THIEF_ALERT_FILE) == 0:
            try:
                tts = gTTS(text=self.THIEF_TEXT, lang=self.LANG)
                tts.save(self.THIEF_ALERT_FILE)
            except: pass

        if not os.path.exists(self.STOLEN_ALERT_FILE) or os.path.getsize(self.STOLEN_ALERT_FILE) == 0:
            try:
                tts = gTTS(text=self.STOLEN_TEXT, lang=self.LANG)
                tts.save(self.STOLEN_ALERT_FILE)
            except: pass

    def play_sound(self, file_path):
        if time.time() - self.last_alert_time < self.COOLDOWN_SECONDS:
            return
        
        if pygame.mixer.music.get_busy():
            return
        
        try:
            if os.path.exists(file_path):
                print(f"🔊 MEMUTAR ALARM: {file_path}")
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                self.last_alert_time = time.time()
        except Exception as e:
            winsound.Beep(1000, 500)

    def run(self):
        print("Menyiapkan kamera...")
        time.sleep(2)
        
        print("--- KALIBRASI BACKGROUND (3 Detik) ---")
        print("Pastikan Ruangan AMAN (Tidak ada orang).")
        time.sleep(3)
        
        ret, frame_bg = self.cap.read()
        if not ret: 
            print("GAGAL MEMBUKA KAMERA! Cek IP atau Koneksi.")
            return
        
        # Resize frame jika resolusi IP Cam kegedean (opsional, biar tidak berat)
        # Tapi biar codingan simple, kita pakai resolusi asli atau resize di loop
        
        frame_bg = cv2.resize(frame_bg, (640, 480))
        gray_bg = cv2.cvtColor(frame_bg, cv2.COLOR_BGR2GRAY)
        gray_bg = cv2.GaussianBlur(gray_bg, (21, 21), 0)
        
        # FIX: Jangan set ke time.time(), set ke 0.
        # Agar saat baru nyala tidak dianggap "Baru saja ada orang".
        self.last_motion_time = 0 
        
        print("SISTEM PINTAR AKTIF!")
        print("PENTING: Pastikan HP diletakkan (Jangan dipegang tangan agar tidak goyang).")
        print("Suara alarm akan keluar dari LAPTOP.")
        print("Tekan 'q' untuk Keluar.")

        while self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret: break

            frame = cv2.resize(frame, (640, 480)) # Paksa resize biar ringan

            # 1. AI DETECTION (YOLO)
            # Conf dinaikkan ke 0.60 biar lebih ketat (anti hantu)
            results = self.model(frame, verbose=False, conf=0.60)
            
            person_detected = False
            person_boxes = []
            
            # Gambar visual AI
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = self.model.names[cls_id]

                    if cls_id == 0: # Person
                        person_detected = True
                        self.last_motion_time = time.time()
                        person_boxes.append((x1, y1, x2, y2)) # Simpan lokasi orang
                        
                        # Visual: Biru
                        cv2.rectangle(frame, (x1, y1), (x2, y2), self.COLOR_THIEF, 2)
                        cv2.putText(frame, f"PERSON {conf:.2f}", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_THIEF, 2)
                    else:
                        # Visual: Hijau (Barang)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), self.COLOR_SAFE, 2)
                        cv2.putText(frame, f"{name} {conf:.2f}", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_SAFE, 2)

            # 2. DETEKSI BARANG HILANG (Background Subtraction)
            gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_curr = cv2.GaussianBlur(gray_curr, (21, 21), 0)
            
            diff = cv2.absdiff(gray_bg, gray_curr)
            thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)[1]
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            item_missing = False
            
            for c in contours:
                area = cv2.contourArea(c)
                # Filter ukuran barang beneran (1000 - 25000)
                if 1000 < area < 25000:
                    x,y,w,h = cv2.boundingRect(c)
                    if float(w)/h > 6: continue 

                    # CEK INTERSEKSI: Apakah perubahan ini adalah ORANGNYA?
                    is_person_moving = False
                    
                    # Kotak Contour
                    ctx1, cty1, ctx2, cty2 = x, y, x+w, y+h
                    
                    for (px1, py1, px2, py2) in person_boxes:
                        # Hitung Overlap Rectangle
                        ox1 = max(ctx1, px1)
                        oy1 = max(cty1, py1)
                        ox2 = min(ctx2, px2)
                        oy2 = min(cty2, py2)
                        
                        overlap_w = max(0, ox2 - ox1)
                        overlap_h = max(0, oy2 - oy1)
                        overlap_area = overlap_w * overlap_h
                        
                        # Jika overlapping area > 20% dari area contour, anggap itu orang
                        if overlap_area > (area * 0.2):
                            is_person_moving = True
                            break
                    
                    # HANYA anggap barang hilang jika BUKAN orang yang gerak
                    if not is_person_moving:
                        cv2.rectangle(frame, (x,y), (x+w,y+h), self.COLOR_ITEM_MISSING, 2)
                        cv2.putText(frame, "ITEM GONE", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_ITEM_MISSING, 2)
                        item_missing = True

            # 3. LOGIC ALARM
            status_text = "Aman"
            color_text = self.COLOR_SAFE

            # SKENARIO 1: ADA BARANG HILANG (Validasi: Bukan Badan Orang) -> PRIORITAS TINGGI
            if item_missing and (time.time() - self.last_motion_time < 15):
                status_text = "BARANG HILANG!"
                color_text = self.COLOR_ITEM_MISSING
                print("⚠ BARANG HILANG!")
                self.play_sound(self.STOLEN_ALERT_FILE)
            
            # SKENARIO 2: TIDAK ADA BARANG HILANG, TAPI ADA ORANG
            elif person_detected:
                status_text = "PENCURI TERDETEKSI!"
                color_text = self.COLOR_THIEF
                print("⚠ PENCURI TERDETEKSI!")
                self.play_sound(self.THIEF_ALERT_FILE)

            # UI Text
            cv2.putText(frame, f"Status: {status_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_text, 2)
            cv2.imshow("Security System (Class Based)", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                gray_bg = gray_curr.copy()
                print("Background Reset!")

        self.cap.release()
        cv2.destroyAllWindows()
        try: pygame.mixer.quit()
        except: pass

if __name__ == "__main__":
    try:
        os.system('cls')
        print("=== SECURITY SYSTEM AI ===")
        print("[1] Pakai Kamera Laptop WebCam")
        print("[2] Pakai Kamera HP (IP Webcam)")
        pilihan = input("Pilih (1/2): ")
        
        src = 0
        if pilihan == '2':
            print("Mode Kamera HP (IP Webcam)")
            # IP Hardcoded sesuai request user
            src = "http://10.146.142.114:8080/video"
            print(f"Connecting ke: {src} ...")
        
        app = SecuritySystem(source=src)
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        input("Enter to exit...")
