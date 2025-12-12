import PyInstaller.__main__
import os
import shutil

# Build configuration
APP_NAME = "Supanikki"
MAIN_SCRIPT = "main.py"
ICON_FILE = "app_icon.ico"  # We will convert png to ico if needed, or assume ico exists
# Note: generate_image creates a png. I might need to convert it or use pillow.
# I will assume I can create the ICO from the PNG in this script if it doesn't exist?
# Actually, let's just use the PNG if PyInstaller supports it (it usually wants ICO for Windows).
# I'll add code to convert PNG to ICO using Pillow in this script.

def build():
    print("Building Supanikki...")

    # Ensure icon exists as ICO
    if not os.path.exists("app_icon.ico") and os.path.exists("app_icon.png"):
        print("Converting PNG to ICO...")
        from PIL import Image
        img = Image.open("app_icon.png")
        img.save("app_icon.ico", format="ICO", sizes=[(256, 256)])
    
    # PyInstaller arguments
    args = [
        MAIN_SCRIPT,
        f'--name={APP_NAME}',
        '--noconsole',
        '--onefile',
        f'--icon={ICON_FILE}',
        '--clean',
        # Add data if needed, but we are using external config files so no --add-data for those.
        # However, if there are other assets (like images) they should be added.
        # Main.py generates an icon in code, so no external assets for that.
        # We rely on configs being strictly NEXT TO the exe.
    ]
    
    PyInstaller.__main__.run(args)
    
    print("Build complete.")
    print("Don't forget to copy credentials.json, token.json, and settings.json to the dist directory before running!")

if __name__ == "__main__":
    build()
