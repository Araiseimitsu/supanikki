import os
import time
import time
import threading
import traceback
from datetime import datetime
from urllib.parse import urlparse

import gspread
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config
from offline_queue import OfflineQueue

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    # 既存フォルダ配下へのアップロードやフォルダ存在確認のため Drive 全体へアクセス
    # （共有権限は本アプリ側では変更しない＝自分のみ閲覧のまま）
    "https://www.googleapis.com/auth/drive",
]


def _normalize_drive_folder_id(value: str) -> str:
    """
    config.DRIVE_FOLDER_ID に「フォルダID」または「フォルダURL」が入っていても、
    フォルダIDを返す。
    """
    if not value:
        return ""

    v = value.strip().strip('"').strip("'")
    # URLっぽい場合は /drive/folders/<id> を抜く
    if "drive.google.com" in v:
        try:
            p = urlparse(v)
            parts = [x for x in p.path.split("/") if x]
            # 例: /drive/folders/<id>
            if len(parts) >= 3 and parts[0] == "drive" and parts[1] == "folders":
                return parts[2]
        except Exception:
            pass

    # クエリが付いているだけなら切り落とす
    if "?" in v:
        v = v.split("?", 1)[0]
    return v


class SheetManager:
    def __init__(self):
        self.creds = None
        self.client = None
        self.spreadsheet = None
        self.sheet = None
        self.sheet_title = getattr(config, "SHEET_NAME", "")
        self.drive = None
        # We don't verify on init to allow app to start without crashing if config is incomplete
        self.is_authenticated = False
        self.queue = OfflineQueue()

    def authenticate(self):
        try:
            if os.path.exists(config.TOKEN_FILE):
                # まずは token.json に入っているスコープのまま読み込む（ここでSCOPESを渡すと、
                # refresh時に「持っていないスコープ」で更新を試みて invalid_scope になり得る）
                try:
                    if os.path.getsize(config.TOKEN_FILE) == 0:
                        raise ValueError("token.json is empty")
                    self.creds = Credentials.from_authorized_user_file(config.TOKEN_FILE)
                except Exception:
                    # 空/壊れた token.json は削除して再認証へ
                    self.creds = None
                    try:
                        os.remove(config.TOKEN_FILE)
                    except Exception:
                        pass

            # スコープが不足している場合（Drive追加など）は再認証が必要
            if (
                self.creds
                and hasattr(self.creds, "has_scopes")
                and not self.creds.has_scopes(SCOPES)
            ):
                print(
                    "Existing token.json does not have required scopes. Re-authentication is required."
                )
                self.creds = None

            # 期限切れなら token.json を削除して再認証へ
            if self.creds and getattr(self.creds, "expired", False):
                print("Token expired. Removing token.json and re-authenticating.")
                self.creds = None
                try:
                    os.remove(config.TOKEN_FILE)
                except Exception:
                    pass

            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    try:
                        self.creds.refresh(Request())
                    except RefreshError:
                        print(
                            "Refresh token is no longer valid. "
                            "Re-authentication is required."
                        )
                        self.creds = None
                        try:
                            os.remove(config.TOKEN_FILE)
                        except Exception:
                            pass

                # Refreshに失敗した場合や初回は再認証へ
                if not self.creds or not self.creds.valid:
                    if not os.path.exists(config.CREDENTIALS_FILE):
                        print(
                            f"Credentials file '{config.CREDENTIALS_FILE}' not found."
                        )
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(
                        config.CREDENTIALS_FILE, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0, open_browser=True)

                with open(config.TOKEN_FILE, "w") as token:
                    token.write(self.creds.to_json())

            self.client = gspread.authorize(self.creds)
            # Drive API（v3）
            self.drive = build(
                "drive", "v3", credentials=self.creds, cache_discovery=False
            )
            self.is_authenticated = True
            return True
        except Exception as e:
            print(f"Authentication failed: {e}")
            print(traceback.format_exc())
            return False

    def connect_sheet(self):
        if not self.is_authenticated:
            if not self.authenticate():
                return False

        if config.SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
            print("Spreadsheet ID not configured.")
            return False

        try:
            self.spreadsheet = self.client.open_by_key(config.SPREADSHEET_ID)
            if self.sheet_title:
                try:
                    self.sheet = self.spreadsheet.worksheet(self.sheet_title)
                except Exception:
                    print(f"Sheet '{self.sheet_title}' not found. Falling back to first sheet.")
                    self.sheet = self.spreadsheet.sheet1
                    self.sheet_title = self.sheet.title
            else:
                self.sheet = self.spreadsheet.sheet1
                self.sheet_title = self.sheet.title
            return True
        except Exception as e:
            print(f"Error connecting to sheet: {e}")
            print(traceback.format_exc())
            return False

    def get_sheet_titles(self):
        if not self.spreadsheet:
            if not self.connect_sheet():
                return []

        try:
            return [ws.title for ws in self.spreadsheet.worksheets()]
        except Exception as e:
            print(f"Failed to list sheets: {e}")
            return []

    def set_sheet_by_title(self, title: str) -> bool:
        if not title:
            return False

        if not self.spreadsheet:
            if not self.connect_sheet():
                return False

        try:
            self.sheet = self.spreadsheet.worksheet(title)
            self.sheet_title = title
            return True
        except Exception as e:
            print(f"Failed to select sheet '{title}': {e}")
            return False

    def append_log(self, text):
        if not self.sheet:
            if not self.connect_sheet():
                print("Connection failed. Adding to offline queue.")
                self.queue.add(text)
                return False

        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.sheet.append_row([timestamp, text])
            # 成功したら、溜まっているキューも処理を試みる（別スレッドが良いが、ここでは簡易的に呼ぶ）
            # 実際にはレスポンス低下を防ぐため、スレッドで呼ぶべき
            threading.Thread(target=self.process_queue, daemon=True).start()
            return True
        except Exception as e:
            print(f"Error appending row: {e}")
            # Try to reconnect once
            if self.connect_sheet():
                try:
                    self.sheet.append_row([timestamp, text])
                    threading.Thread(target=self.process_queue, daemon=True).start()
                    return True
                except:
                    pass
            
            # If all else fails, add to queue
            print("Failed to send. Adding to offline queue.")
            self.queue.add(text, timestamp)
            return False

    def process_queue(self):
        """queued items の再送を試みる"""
        if self.queue.is_empty():
            return

        if not self.sheet:
             if not self.connect_sheet():
                 return

        # キューの先頭から順に処理
        print(f"Processing offline queue ({len(self.queue.get_all())} items)...")
        while not self.queue.is_empty():
            item = self.queue.peek()
            if not item:
                break
            
            try:
                # タイムスタンプは元のものを使用
                self.sheet.append_row([item["timestamp"], item["text"]])
                print(f"Recovered item sent: {item['text'][:10]}...")
                self.queue.pop() # 成功したら消す
                time.sleep(1) # API制限考慮
            except Exception as e:
                print(f"Retry failed: {e}")
                # 接続切れなどの場合はループを抜けて次回に持ち越し
                break

    def upload_file_to_drive(self, file_path: str) -> str:
        """
        指定ファイルをGoogle Driveへアップロードし、webViewLink(URL) を返す。
        - 共有権限は変更しない（既定：自分のみ閲覧）
        - config.DRIVE_FOLDER_ID が空でなければそのフォルダ配下へ保存
        """
        if not self.is_authenticated:
            if not self.authenticate():
                raise RuntimeError("Google authentication failed")

        if not self.drive:
            raise RuntimeError("Drive service is not initialized")

        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)

        file_name = os.path.basename(file_path)
        metadata = {"name": file_name}

        folder_id_raw = getattr(config, "DRIVE_FOLDER_ID", "") or ""
        folder_id = _normalize_drive_folder_id(folder_id_raw)
        if folder_id:
            # フォルダが存在し、アクセス可能かを事前にチェック（URL/IDの貼り間違いの原因特定用）
            try:
                self.drive.files().get(
                    fileId=folder_id,
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
            except Exception as e:
                raise RuntimeError(
                    "DRIVE_FOLDER_ID のフォルダが見つからないか、アクセス権がありません。"
                    " Driveの共有設定/権限、またはフォルダURL/IDを確認してください。"
                ) from e
            metadata["parents"] = [folder_id]

        media = MediaFileUpload(file_path, resumable=True)
        created = (
            self.drive.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )

        file_id = created.get("id")
        return (
            created.get("webViewLink")
            or f"https://drive.google.com/file/d/{file_id}/view"
        )


if __name__ == "__main__":
    # simple test
    sm = SheetManager()
    if sm.authenticate():
        print("Auth successful")
    else:
        print("Auth failed")
