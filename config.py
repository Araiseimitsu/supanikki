import os
import sys

# Determine if we are running in a frozen bundle (PyInstaller) or standard script
if getattr(sys, "frozen", False):
    # If frozen, the executable dir is here
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # If script, the script dir is here
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SPREADSHEET_ID = "1k4FX3oR-ICAgHoFvkd0ZG-nYzY0p3zCahbUcG6BHVts"
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
HOTKEY = "ctrl+shift+space"

# Google Drive: アップロード先フォルダ（空文字ならマイドライブ直下）
# 例) https://drive.google.com/drive/folders/<FOLDER_ID> の <FOLDER_ID>
# DRIVE_FOLDER_ID = 'https://drive.google.com/drive/folders/1dUOuIMYAkY5nnM0kJYu1bm6pMysUQRZb?usp=drive_link'
DRIVE_FOLDER_ID = "1dUOuIMYAkY5nnM0kJYu1bm6pMysUQRZb"
