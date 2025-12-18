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
from local_history import LocalHistory

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
    history_manager = LocalHistory()

    settings = load_settings()
    hotkey_value = settings.get("hotkey") or config.HOTKEY
    if "sheet_next_hotkey" in settings:
        sheet_next_hotkey = (settings.get("sheet_next_hotkey") or "").strip()
    else:
        sheet_next_hotkey = config.SHEET_NEXT_HOTKEY

    if "sheet_prev_hotkey" in settings:
        sheet_prev_hotkey = (settings.get("sheet_prev_hotkey") or "").strip()
    else:
        sheet_prev_hotkey = config.SHEET_PREV_HOTKEY

    def on_submit(text):
        print(f"Logging: {text}")
        history_manager.add(text) # Save to local history
        if sheet_manager.append_log(text):
            print("Successfully logged to Sheet.")
        else:
            print("Failed to log to Sheet. Check config/connection.")

    def on_upload(file_path: str) -> str:
        return sheet_manager.upload_file_to_drive(file_path)

    window = None

    def get_current_sheet_name() -> str:
        return sheet_manager.sheet_title or settings.get("sheet_name", "")

    def set_active_sheet(title: str) -> bool:
        if sheet_manager.set_sheet_by_title(title):
            settings["sheet_name"] = title
            save_settings(settings)
            print(f"Active sheet set to: {title}")
            if window:
                window.update_sheet_name(title)
            return True
        print(f"Failed to select sheet: {title}")
        return False

    def cycle_sheet(direction: int):
        titles = sheet_manager.get_sheet_titles()
        if not titles:
            print("No sheets available or failed to connect.")
            return

        current = sheet_manager.sheet_title
        if not current and sheet_manager.sheet:
            try:
                current = sheet_manager.sheet.title
            except Exception:
                current = None

        if current in titles:
            idx = titles.index(current)
        else:
            idx = 0

        new_title = titles[(idx + direction) % len(titles)]
        set_active_sheet(new_title)
        schedule_hotkey_reset()

    # Initialize UI
    window = InputWindow(
        submit_callback=on_submit, 
        upload_callback=on_upload,
        history_manager=history_manager,
        sheet_name_provider=get_current_sheet_name,
    )

    # ホットキーの状態管理
    hotkey_listener = None
    hotkey_lock = threading.Lock()
    last_trigger_time = [0]  # リスト参照で共有
    debounce_interval = 0.3  # 300ms以内の連続呼び出しを防ぐ
    last_hotkey_reset = [0]
    hotkey_reset_lock = threading.Lock()
    hotkey_reset_interval = 0.5  # 連続リセット抑制

    def schedule_hotkey_reset():
        """押下状態のスタック対策としてホットキーを再登録する"""
        now = time.time()
        if now - last_hotkey_reset[0] < hotkey_reset_interval:
            return
        last_hotkey_reset[0] = now

        def worker():
            time.sleep(0.05)
            with hotkey_reset_lock:
                register_hotkey()

        threading.Thread(target=worker, daemon=True).start()

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
        finally:
            schedule_hotkey_reset()

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

                hotkey_map = {}
                registered_hotkeys = set()

                # Toggle window hotkey
                pynput_hotkey = convert_hotkey_to_pynput(hotkey_value)
                if pynput_hotkey:
                    hotkey_map[pynput_hotkey] = toggle_window
                    registered_hotkeys.add(pynput_hotkey)
                else:
                    print(f"Invalid hotkey format: {hotkey_value}")

                # Sheet switching hotkeys
                if sheet_next_hotkey:
                    pynput_next = convert_hotkey_to_pynput(sheet_next_hotkey)
                    if pynput_next:
                        if pynput_next in registered_hotkeys:
                            print("sheet_next_hotkey conflicts with existing hotkey; skipping.")
                        else:
                            hotkey_map[pynput_next] = lambda: cycle_sheet(1)
                            registered_hotkeys.add(pynput_next)
                    else:
                        print(f"Invalid sheet_next_hotkey: {sheet_next_hotkey}")

                if sheet_prev_hotkey:
                    pynput_prev = convert_hotkey_to_pynput(sheet_prev_hotkey)
                    if pynput_prev:
                        if pynput_prev in registered_hotkeys:
                            print("sheet_prev_hotkey conflicts with existing hotkey; skipping.")
                        else:
                            hotkey_map[pynput_prev] = lambda: cycle_sheet(-1)
                            registered_hotkeys.add(pynput_prev)
                    else:
                        print(f"Invalid sheet_prev_hotkey: {sheet_prev_hotkey}")

                if not hotkey_map:
                    print("No valid hotkeys to register.")
                    return

                # GlobalHotKeysを使用して登録
                try:
                    hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
                    hotkey_listener.start()
                    print("Hotkeys registered successfully.")
                except Exception as e:
                    print(f"Failed to register hotkeys: {e}")
                    if pynput_hotkey:
                        try:
                            hotkey_listener = keyboard.GlobalHotKeys({pynput_hotkey: toggle_window})
                            hotkey_listener.start()
                            print("Hotkey registered successfully (toggle only).")
                        except Exception as e2:
                            print(f"Failed to register toggle hotkey only: {e2}")
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
        base_url = f"https://docs.google.com/spreadsheets/d/{config.SPREADSHEET_ID}"
        url = base_url
        try:
            if not sheet_manager.sheet:
                sheet_manager.connect_sheet()
            if sheet_manager.sheet:
                gid = getattr(sheet_manager.sheet, "id", None)
                if gid is not None:
                    url = f"{base_url}/edit#gid={gid}"
        except Exception:
            pass
        webbrowser.open(url)

    def on_next_sheet(icon, item):
        cycle_sheet(1)

    def on_prev_sheet(icon, item):
        cycle_sheet(-1)

    def on_change_sheet(icon, item):
        def prompt():
            try:
                import tkinter.messagebox as mb
                import customtkinter as ctk

                titles = sheet_manager.get_sheet_titles()
                if not titles:
                    mb.showerror("エラー", "シート一覧の取得に失敗しました。")
                    return

                current = sheet_manager.sheet_title or ""
                hint = " / ".join(titles)
                dialog = ctk.CTkInputDialog(
                    text=f"切り替えるシート名を入力してください:\n{hint}\n\n現在: {current}",
                    title="シート変更",
                )
                new_title = (dialog.get_input() or "").strip()
                if not new_title:
                    return
                if new_title not in titles:
                    mb.showerror("エラー", f"シートが見つかりません: {new_title}")
                    return
                set_active_sheet(new_title)
            except Exception as e:
                print(f"Sheet change dialog error: {e}")

        try:
            window.root.after(0, prompt)
        except Exception:
            prompt()

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
        pystray.MenuItem("Next Sheet", on_next_sheet),
        pystray.MenuItem("Previous Sheet", on_prev_sheet),
        pystray.MenuItem("Change Sheet", on_change_sheet),
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
