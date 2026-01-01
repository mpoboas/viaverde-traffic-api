#!/usr/bin/env python3
"""
Example: Interactive camera viewer with error handling.

This script demonstrates:
1. Error handling with custom exceptions
2. Interactive camera selection
3. PIL Image display (requires Pillow)
"""

from viaverde_traffic import (
    ViaVerdeTrafficAPI,
    ViaVerdeConnectionError,
    ViaVerdeAPIError,
    ViaVerdeImageError,
)

def main():
    try:
        api = ViaVerdeTrafficAPI()
        
        print("Fetching camera list...")
        cameras = api.get_all_cameras()
        print(f"Found {len(cameras)} cameras\n")
        
    except ViaVerdeConnectionError as e:
        print(f"❌ Connection error: {e}")
        print("Please check your internet connection.")
        return
    except ViaVerdeAPIError as e:
        print(f"❌ API error: {e}")
        return
    
    while True:
        # Show menu
        print("\n" + "=" * 50)
        print("ViaVerde Traffic Camera Viewer")
        print("=" * 50)
        print("1. List all cameras")
        print("2. Search cameras")
        print("3. View camera by ID")
        print("4. Exit")
        print("=" * 50)
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == "1":
            print("\nAll cameras:")
            for cam in cameras:
                print(f"  [{cam['nomeAe']:4}] {cam['nomeCamara']} (ID: {cam['idCamara']})")
        
        elif choice == "2":
            search = input("Search term: ").strip()
            results = api.find_cameras(search, cameras=cameras)
            print(f"\nFound {len(results)} cameras:")
            for cam in results:
                print(f"  [{cam['nomeAe']:4}] {cam['nomeCamara']} (ID: {cam['idCamara']})")
        
        elif choice == "3":
            try:
                cam_id = int(input("Camera ID: ").strip())
                
                print(f"Fetching camera {cam_id}...")
                
                try:
                    img = api.get_camera_image_pil(cam_id)
                    print(f"Image size: {img.size}")
                    img.show()
                except ImportError:
                    # Pillow not installed, save to file instead
                    filename = f"camera_{cam_id}.jpg"
                    api.save_camera_image(cam_id, filename)
                    print(f"Image saved to: {filename}")
                except ViaVerdeImageError as e:
                    print(f"❌ Image error: {e}")
                    
            except ValueError:
                print("Invalid ID!")
            except ViaVerdeAPIError as e:
                print(f"❌ API error: {e}")
        
        elif choice == "4":
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice!")


if __name__ == "__main__":
    main()
