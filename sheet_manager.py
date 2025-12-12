import os.path
import traceback
from datetime import datetime
from urllib.parse import urlparse

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

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
        self.sheet = None
        self.drive = None
        # We don't verify on init to allow app to start without crashing if config is incomplete
        self.is_authenticated = False

    def authenticate(self):
        try:
            if os.path.exists(config.TOKEN_FILE):
                # まずは token.json に入っているスコープのまま読み込む（ここでSCOPESを渡すと、
                # refresh時に「持っていないスコープ」で更新を試みて invalid_scope になり得る）
                self.creds = Credentials.from_authorized_user_file(config.TOKEN_FILE)

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

            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if not os.path.exists(config.CREDENTIALS_FILE):
                        print(
                            f"Credentials file '{config.CREDENTIALS_FILE}' not found."
                        )
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(
                        config.CREDENTIALS_FILE, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)

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
            self.sheet = self.client.open_by_key(config.SPREADSHEET_ID).sheet1
            return True
        except Exception as e:
            print(f"Error connecting to sheet: {e}")
            print(traceback.format_exc())
            return False

    def append_log(self, text):
        if not self.sheet:
            if not self.connect_sheet():
                return False

        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.sheet.append_row([timestamp, text])
            return True
        except Exception as e:
            print(f"Error appending row: {e}")
            # Try to reconnect once
            if self.connect_sheet():
                try:
                    self.sheet.append_row([timestamp, text])
                    return True
                except:
                    return False
            return False

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
