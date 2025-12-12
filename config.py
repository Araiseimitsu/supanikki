import json
import os
import sys

# Determine if we are running in a frozen bundle (PyInstaller) or standard script
if getattr(sys, "frozen", False):
    # If frozen, the executable dir is here
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # If script, the script dir is here
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 外部設定ファイルのパス
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")


def load_settings():
    """外部設定ファイルから設定を読み込む"""
    if not os.path.exists(SETTINGS_FILE):
        raise FileNotFoundError(
            f"設定ファイルが見つかりません: {SETTINGS_FILE}\n"
            "settings.json を同じディレクトリに配置してください。"
        )

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)

        # 必須項目のチェック
        required_fields = [
            "spreadsheet_id",
            "credentials_file",
            "drive_folder_id",
            "hotkey",
        ]
        missing_fields = [field for field in required_fields if field not in settings]

        if missing_fields:
            raise ValueError(
                f"settings.json に必須項目が不足しています: {', '.join(missing_fields)}"
            )

        return settings
    except json.JSONDecodeError as e:
        raise ValueError(f"settings.json の形式が正しくありません: {e}")
    except Exception as e:
        raise Exception(f"設定ファイルの読み込みに失敗しました: {e}")


# 設定を読み込み
_settings = load_settings()

# 各設定値（外部設定ファイルから読み込み）
SPREADSHEET_ID = _settings["spreadsheet_id"]
CREDENTIALS_FILE = os.path.join(BASE_DIR, _settings["credentials_file"])
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
HOTKEY = _settings["hotkey"]
DRIVE_FOLDER_ID = _settings["drive_folder_id"]
