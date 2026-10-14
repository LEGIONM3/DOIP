import os
import sys
import urllib.request
import time

DEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "videos", "surveillance")
os.makedirs(DEST_DIR, exist_ok=True)

VIDEOS = [
    # 1. Perimeter & Security
    {
        "filename": "cam-01.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/1.mp4",
        "title": "Perimeter North Gate",
        "sector": "PERIMETER",
    },
    {
        "filename": "cam-02.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/2.mp4",
        "title": "East Fence Sensor Sector",
        "sector": "PERIMETER",
    },
    {
        "filename": "cam-03.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/10.mp4",
        "title": "Watchtower 03 Approach",
        "sector": "PERIMETER",
    },
    {
        "filename": "cam-04.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/11.mp4",
        "title": "Forward Observation Post Bravo",
        "sector": "PERIMETER",
    },
    {
        "filename": "cam-05.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/12.mp4",
        "title": "North Berm Restricted Zone",
        "sector": "PERIMETER",
    },
    {
        "filename": "cam-06.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/14.mp4",
        "title": "Sally Port Vehicle Air-Lock",
        "sector": "PERIMETER",
    },

    # 2. Convoy & Checkpoints
    {
        "filename": "cam-07.mp4",
        "url": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/car-detection.mp4",
        "title": "MSR Iron Supply Route",
        "sector": "TRANSIT",
    },
    {
        "filename": "cam-08.mp4",
        "url": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/person-bicycle-car-detection.mp4",
        "title": "Tactical Checkpoint Alpha",
        "sector": "TRANSIT",
    },
    {
        "filename": "cam-09.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam2/1.mp4",
        "title": "Corridor Bravo Checkpoint",
        "sector": "TRANSIT",
    },
    {
        "filename": "cam-10.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam2/10.mp4",
        "title": "Logistics Depot Transit Road",
        "sector": "TRANSIT",
    },
    {
        "filename": "cam-11.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam2/11.mp4",
        "title": "Munitions Loading Bay Ramp",
        "sector": "TRANSIT",
    },
    {
        "filename": "cam-12.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam2/12.mp4",
        "title": "Heavy Fuel Depot Gate",
        "sector": "TRANSIT",
    },

    # 3. Aerial UAV Feeds
    {
        "filename": "cam-13.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/16.mp4",
        "title": "UAV Valkyrie-1 Overflight",
        "sector": "AERIAL_UAV",
    },
    {
        "filename": "cam-14.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/17.mp4",
        "title": "UAV Valkyrie-2 Sector Scan",
        "sector": "AERIAL_UAV",
    },
    {
        "filename": "cam-15.mp4",
        "url": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/people-detection.mp4",
        "title": "FLIR Optical Aerial Grid",
        "sector": "AERIAL_UAV",
    },
    {
        "filename": "cam-16.mp4",
        "url": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/one-by-one-person-detection.mp4",
        "title": "Perimeter Sweep Sector 7",
        "sector": "AERIAL_UAV",
    },
    {
        "filename": "cam-17.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/18.mp4",
        "title": "Gimbal Sensor Tracker",
        "sector": "AERIAL_UAV",
    },
    {
        "filename": "cam-18.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam1/19.mp4",
        "title": "High-Altitude Lookout",
        "sector": "AERIAL_UAV",
    },

    # 4. Facility Interior & Hubs
    {
        "filename": "cam-19.mp4",
        "url": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/worker-zone-detection.mp4",
        "title": "Command Bunker Hall",
        "sector": "FACILITY",
    },
    {
        "filename": "cam-20.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam2/13.mp4",
        "title": "Armory & Vault Entry",
        "sector": "FACILITY",
    },
    {
        "filename": "cam-21.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam2/14.mp4",
        "title": "Comms Server Hub",
        "sector": "FACILITY",
    },
    {
        "filename": "cam-22.mp4",
        "url": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/store-aisle-detection.mp4",
        "title": "Medical Depot Storage",
        "sector": "FACILITY",
    },
    {
        "filename": "cam-23.mp4",
        "url": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/face-demographics-walking.mp4",
        "title": "Biometric Screening Portal",
        "sector": "FACILITY",
    },
    {
        "filename": "cam-24.mp4",
        "url": "https://raw.githubusercontent.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos/master/violence-detection-dataset/non-violent/cam2/16.mp4",
        "title": "Operations Vestibule",
        "sector": "FACILITY",
    },
]

def download_all():
    print(f"Beginning download of {len(VIDEOS)} surveillance videos to {DEST_DIR}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    success = 0
    for idx, v in enumerate(VIDEOS, 1):
        target = os.path.join(DEST_DIR, v["filename"])
        if os.path.exists(target) and os.path.getsize(target) > 50000:
            print(f"[{idx}/{len(VIDEOS)}] Exists ({os.path.getsize(target)} bytes): {v['filename']}")
            success += 1
            continue

        print(f"[{idx}/{len(VIDEOS)}] Downloading {v['title']} ({v['filename']})...")
        try:
            req = urllib.request.Request(v["url"], headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                with open(target, "wb") as f:
                    f.write(data)
            print(f"       -> Saved {len(data)} bytes ({round(len(data)/(1024*1024), 2)} MB)")
            success += 1
        except Exception as e:
            print(f"       -> Failed: {e}")

    print(f"\nDone: {success}/{len(VIDEOS)} videos ready in {DEST_DIR}")

if __name__ == "__main__":
    download_all()
