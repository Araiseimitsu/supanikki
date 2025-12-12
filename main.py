import json
import os
import subprocess
import sys
import threading
import time
import webbrowser

import pystray
from PIL import Image, ImageDraw
from pynput import keyboard

import config
from sheet_manager import SheetManager
from ui import InputWindow

# Ensure we can find local modules

SETTINGS_FILE = os.path.join(config.BASE_DIR, "settings.json")


def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Failed to load settings: {e}")
    return {}


def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save settings: {e}")


def create_image():
    # Generate an icon with a 'S'
    width = 64
    height = 64
    color1 = (0, 120, 215)
    color2 = (255, 255, 255)

    image = Image.new("RGB", (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 4, height // 4, 3 * width // 4, 3 * height // 4), fill=color2
    )
    return image


def main():
    print("Starting Supanikki...")

    # Initialize Sheet Manager
    sheet_manager = SheetManager()

    settings = load_settings()
    hotkey_value = settings.get("hotkey") or config.HOTKEY

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

    # ホットキーの状態管理
    hotkey_listener = None
    hotkey_lock = threading.Lock()
    last_trigger_time = [0]  # リスト参照で共有
    debounce_interval = 0.3  # 300ms以内の連続呼び出しを防ぐ

    def toggle_window():
        """ホットキー押下時のコールバック（デバウンス処理付き）"""
        current_time = time.time()
        if current_time - last_trigger_time[0] < debounce_interval:
            return  # 連続呼び出しを無視
        last_trigger_time[0] = current_time

        try:
            window.thread_safe_toggle()
        except Exception as e:
            print(f"Hotkey callback error: {e}")

    def convert_hotkey_to_pynput(hotkey_str: str):
        """
        ホットキー文字列をpynput形式に変換
        例: 'ctrl+shift+space' -> '<ctrl>+<shift>+<space>'
        """
        parts = [p.strip().lower() for p in hotkey_str.split("+")]
        pynput_parts = []

        for part in parts:
            if part in ("ctrl", "control"):
                pynput_parts.append("<ctrl>")
            elif part in ("shift",):
                pynput_parts.append("<shift>")
            elif part in ("alt",):
                pynput_parts.append("<alt>")
            elif part in ("win", "windows", "cmd", "super"):
                pynput_parts.append("<cmd>")
            elif part == "space":
                pynput_parts.append("<space>")
            elif part == "enter":
                pynput_parts.append("<enter>")
            elif part == "esc":
                pynput_parts.append("<esc>")
            elif part == "tab":
                pynput_parts.append("<tab>")
            elif len(part) == 1:
                pynput_parts.append(part)
            else:
                pynput_parts.append(f"<{part}>")

        return "+".join(pynput_parts) if pynput_parts else None

    def register_hotkey():
        """ホットキーを登録（pynput使用）"""
        nonlocal hotkey_listener
        with hotkey_lock:
            try:
                # 既存のリスナーを停止
                if hotkey_listener is not None:
                    try:
                        hotkey_listener.stop()
                    except Exception:
                        pass
                    hotkey_listener = None

                # ホットキーをpynput形式に変換
                pynput_hotkey = convert_hotkey_to_pynput(hotkey_value)
                if not pynput_hotkey:
                    print(f"Invalid hotkey format: {hotkey_value}")
                    return

                # GlobalHotKeysを使用して登録
                hotkey_listener = keyboard.GlobalHotKeys({pynput_hotkey: toggle_window})
                hotkey_listener.start()
                print(
                    f"Hotkey '{hotkey_value}' (pynput: '{pynput_hotkey}') registered successfully."
                )
            except Exception as e:
                print(f"Failed to register hotkey: {e}")
                import traceback

                traceback.print_exc()

    # Setup Global Hotkey
    register_hotkey()

    # ホットキーの監視スレッド（定期的に状態確認して自動復旧）
    def monitor_hotkey():
        while True:
            try:
                time.sleep(60)  # 60秒ごとにチェック
                with hotkey_lock:
                    if hotkey_listener is None or not hotkey_listener.running:
                        print("Hotkey listener is down. Re-registering...")
                        register_hotkey()
            except Exception as e:
                print(f"Hotkey monitor error: {e}")

    monitor_thread = threading.Thread(target=monitor_hotkey, daemon=True)
    monitor_thread.start()

    # Setup System Tray
    def on_quit(icon, item):
        icon.stop()
        with hotkey_lock:
            if hotkey_listener is not None:
                try:
                    hotkey_listener.stop()
                except Exception:
                    pass
        window.quit()

    def on_toggle_tray(icon, item):
        toggle_window()

    def on_open_sheet(icon, item):
        url = f"https://docs.google.com/spreadsheets/d/{config.SPREADSHEET_ID}"
        webbrowser.open(url)

    def on_open_upload_folder(icon, item):
        # Driveのアップロード先フォルダ（config.DRIVE_FOLDER_ID）を開く
        folder_raw = getattr(config, "DRIVE_FOLDER_ID", "") or ""
        folder_raw = folder_raw.strip().strip('"').strip("'")
        if not folder_raw:
            webbrowser.open("https://drive.google.com/drive/my-drive")
            return
        if "drive.google.com" in folder_raw:
            webbrowser.open(folder_raw)
            return
        webbrowser.open(f"https://drive.google.com/drive/folders/{folder_raw}")

    def on_change_hotkey(icon, item):
        # Tkのメインスレッドで入力ダイアログを出す
        def prompt():
            try:
                import tkinter.messagebox as mb

                import customtkinter as ctk

                dialog = ctk.CTkInputDialog(
                    text="新しいショートカットキーを入力してください（例: ctrl+shift+space）",
                    title="ショートカット変更",
                )
                new_hotkey = (dialog.get_input() or "").strip()
                if not new_hotkey:
                    return

                # まず登録できるか試す（パースできるか確認）
                try:
                    test_hotkey = convert_hotkey_to_pynput(new_hotkey)
                    if not test_hotkey:
                        raise ValueError("Invalid hotkey format")
                except Exception as e:
                    try:
                        mb.showerror(
                            "エラー", f"そのショートカットは登録できません: {e}"
                        )
                    except Exception:
                        print(f"Invalid hotkey: {e}")
                    return

                nonlocal hotkey_value, settings
                hotkey_value = new_hotkey
                settings["hotkey"] = new_hotkey
                save_settings(settings)

                # ホットキーを再登録
                register_hotkey()

                # 変更完了を通知し、再起動を促す
                try:
                    result = mb.askyesno(
                        "ショートカット変更完了",
                        f"ショートカットキーを '{new_hotkey}' に変更しました。\n\n"
                        "変更を確実に反映させるため、アプリの再起動を推奨します。\n"
                        "今すぐ再起動しますか？",
                    )
                    if result:
                        on_restart(icon, item)
                except Exception:
                    print(f"Hotkey changed to: {new_hotkey}")

            except Exception as e:
                print(f"Hotkey change dialog error: {e}")

        try:
            window.root.after(0, prompt)
        except Exception:
            prompt()

    def on_restart(icon, item):
        # 新しいプロセスを立ち上げてから終了
        try:
            if getattr(sys, 'frozen', False):
                # If we are an exe, just relaunch the exe
                subprocess.Popen([sys.executable])
            else:
                # If script, run with python interpreter
                subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e:
            print(f"Failed to restart: {e}")
            return
        on_quit(icon, item)

    menu = pystray.Menu(
        pystray.MenuItem("Input", on_toggle_tray),
        pystray.MenuItem("Open Spreadsheet", on_open_sheet),
        pystray.MenuItem("Open Upload Folder", on_open_upload_folder),
        pystray.MenuItem("Change Hotkey", on_change_hotkey),
        pystray.MenuItem("Restart", on_restart),
        pystray.MenuItem("Quit", on_quit),
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
