#!/usr/bin/env python3
"""
Example: Basic usage of the ViaVerde Traffic API.

This script demonstrates how to:
1. Initialize the API client
2. Get a list of all cameras
3. Fetch and save a camera image
"""

from viaverde_traffic import ViaVerdeTrafficAPI

def main():
    # Initialize the API client
    api = ViaVerdeTrafficAPI()

    print("Fetching list of cameras...")
    cameras = api.get_all_cameras()
    print(f"Found {len(cameras)} cameras\n")

    # Display first 10 cameras
    print("First 10 cameras:")
    print("-" * 60)
    for cam in cameras[:10]:
        print(f"[{cam['nomeAe']:4}] {cam['nomeCamara']} (ID: {cam['idCamara']})")
    print("-" * 60)

    # Get first camera image
    if cameras:
        first_camera = cameras[0]
        cam_id = first_camera['idCamara']
        cam_name = first_camera['nomeCamara']
        
        print(f"\nFetching image for '{cam_name}' (ID: {cam_id})...")
        
        # Save image to file
        filename = f"camera_{cam_id}.jpg"
        api.save_camera_image(cam_id, filename)
        print(f"Image saved to: {filename}")


if __name__ == "__main__":
    main()
