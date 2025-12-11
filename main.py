import threading
import keyboard
import pystray
from PIL import Image, ImageDraw
import config
from ui import InputWindow
from sheet_manager import SheetManager
import sys
import os
import webbrowser

# Ensure we can find local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_image():
    # Generate an icon with a 'S'
    width = 64
    height = 64
    color1 = (0, 120, 215)
    color2 = (255, 255, 255)

    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 4, height // 4, 3 * width // 4, 3 * height // 4),
        fill=color2)
    return image

def main():
    print("Starting Supanikki...")
    
    # Initialize Sheet Manager
    sheet_manager = SheetManager()
    
    def on_submit(text):
        print(f"Logging: {text}")
        if sheet_manager.append_log(text):
            print("Successfully logged to Sheet.")
        else:
            print("Failed to log to Sheet. Check config/connection.")

    def on_upload(file_path: str) -> str:
        return sheet_manager.upload_file_to_drive(file_path)

    # Initialize UI
    window = InputWindow(submit_callback=on_submit, upload_callback=on_upload)

    def toggle_window():
        window.thread_safe_toggle()

    # Setup Global Hotkey
    try:
        keyboard.add_hotkey(config.HOTKEY, toggle_window)
        print(f"Hotkey '{config.HOTKEY}' registered.")
    except Exception as e:
        print(f"Failed to register hotkey: {e}")

    # Setup System Tray
    def on_quit(icon, item):
        icon.stop()
        window.quit()

    def on_toggle_tray(icon, item):
        toggle_window()

    def on_open_sheet(icon, item):
        url = f"https://docs.google.com/spreadsheets/d/{config.SPREADSHEET_ID}"
        webbrowser.open(url)

    menu = pystray.Menu(
        pystray.MenuItem('Input', on_toggle_tray),
        pystray.MenuItem('Open Spreadsheet', on_open_sheet),
        pystray.MenuItem('Quit', on_quit)
    )

    icon = pystray.Icon("Supanikki", create_image(), "Supanikki", menu)

    # Run Tray Icon in a separate thread because Tkinter needs the main thread
    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    # Start GUI Main Loop
    print("App is running. Press hotkey to toggle.")
    window.start_mainloop()

if __name__ == "__main__":
    main()
