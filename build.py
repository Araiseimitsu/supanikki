import json
import os
import shutil

import PyInstaller.__main__

# Build configuration
APP_NAME = "Supanikki"
MAIN_SCRIPT = "main.py"
ICON_FILE = "app_icon.ico"


def create_default_settings():
    """デフォルトのsettings.jsonを作成"""
    default_settings = {
        "spreadsheet_id": "YOUR_SPREADSHEET_ID_HERE",
        "credentials_file": "credentials.json",
        "drive_folder_id": "YOUR_DRIVE_FOLDER_ID_HERE",
        "hotkey": "ctrl+shift+space",
    }

    settings_template_path = "settings_template.json"
    with open(settings_template_path, "w", encoding="utf-8") as f:
        json.dump(default_settings, f, ensure_ascii=False, indent=2)

    print(f"デフォルト設定ファイルを作成しました: {settings_template_path}")
    return settings_template_path


def build():
    print("Building Supanikki...")

    # アイコンファイルが存在することを確認（PNGからICOへの変換）
    if not os.path.exists("app_icon.ico") and os.path.exists("app_icon.png"):
        print("PNGをICOに変換中...")
        from PIL import Image

        img = Image.open("app_icon.png")
        img.save("app_icon.ico", format="ICO", sizes=[(256, 256)])

    # デフォルト設定ファイルを作成
    settings_template = create_default_settings()

    # PyInstaller引数
    args = [
        MAIN_SCRIPT,
        f"--name={APP_NAME}",
        "--noconsole",
        "--onefile",
        f"--icon={ICON_FILE}",
        "--clean",
    ]

    PyInstaller.__main__.run(args)

    # distディレクトリにデフォルト設定ファイルをコピー
    dist_dir = "dist"
    if os.path.exists(dist_dir):
        print("\ndistディレクトリにデフォルト設定ファイルをコピー中...")

        # settings_template.jsonをdistにコピー
        dest_settings = os.path.join(dist_dir, "settings.json")
        if os.path.exists(settings_template):
            shutil.copy2(settings_template, dest_settings)
            print(f"  ✓ {dest_settings}")

        # README的な説明ファイルを作成
        readme_path = os.path.join(dist_dir, "README_SETUP.txt")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("=== Supanikki セットアップガイド ===\n\n")
            f.write("1. 必要なファイル:\n")
            f.write("   - Supanikki.exe (実行ファイル)\n")
            f.write("   - credentials.json (Google API認証情報)\n")
            f.write("   - settings.json (アプリケーション設定)\n\n")
            f.write("2. settings.jsonの設定項目:\n")
            f.write("   - spreadsheet_id: Google スプレッドシートID\n")
            f.write(
                "   - credentials_file: 認証情報ファイル名 (デフォルト: credentials.json)\n"
            )
            f.write("   - drive_folder_id: Google Driveアップロード先フォルダID\n")
            f.write(
                "   - hotkey: ショートカットキー (デフォルト: ctrl+shift+space)\n\n"
            )
            f.write("3. 初回起動時の手順:\n")
            f.write("   - credentials.jsonを同じディレクトリに配置してください\n")
            f.write("   - settings.jsonで設定値を変更してください\n")
            f.write("   - Supanikki.exeを実行してください\n\n")
            f.write("注意: token.jsonは初回認証時に自動生成されます\n")
        print(f"  ✓ {readme_path}")

    print("\n" + "=" * 60)
    print("ビルド完了!")
    print("=" * 60)
    print("\n次の手順:")
    print("1. credentials.json を dist/ ディレクトリにコピーしてください")
    print("2. dist/settings.json を必要に応じて編集してください")
    print("3. Supanikki.exe を実行してください")
    print("\n詳細は dist/README_SETUP.txt を参照してください")

    print("\n詳細は dist/README_SETUP.txt を参照してください")


if __name__ == "__main__":
    build()
