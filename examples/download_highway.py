#!/usr/bin/env python3
"""
Example: Download all cameras from a specific highway.

This script demonstrates how to:
1. Search for cameras by highway
2. Download multiple camera images
"""

import os
from viaverde_traffic import ViaVerdeTrafficAPI

def main():
    # Highway to search for
    highway = "A1"
    output_dir = f"cameras_{highway}"
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize API
    api = ViaVerdeTrafficAPI()
    
    print(f"Searching for cameras on {highway}...")
    cameras = api.find_cameras(highway)
    print(f"Found {len(cameras)} cameras\n")
    
    # Download each camera image
    for i, cam in enumerate(cameras, 1):
        cam_id = cam['idCamara']
        cam_name = cam['nomeCamara'].replace(" ", "_").replace("/", "_")
        
        filename = os.path.join(output_dir, f"{cam_id}_{cam_name}.jpg")
        
        print(f"[{i}/{len(cameras)}] Downloading {cam['nomeCamara']}...", end=" ")
        
        try:
            api.save_camera_image(cam_id, filename)
            print("✓")
        except Exception as e:
            print(f"✗ ({e})")
    
    print(f"\nDone! Images saved to: {output_dir}/")


if __name__ == "__main__":
    main()
