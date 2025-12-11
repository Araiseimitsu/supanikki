import os.path
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import config
from datetime import datetime
import traceback

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

class SheetManager:
    def __init__(self):
        self.creds = None
        self.client = None
        self.sheet = None
        # We don't verify on init to allow app to start without crashing if config is incomplete
        self.is_authenticated = False

    def authenticate(self):
        try:
            if os.path.exists(config.TOKEN_FILE):
                self.creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, SCOPES)
            
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if not os.path.exists(config.CREDENTIALS_FILE):
                        print(f"Credentials file '{config.CREDENTIALS_FILE}' not found.")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        config.CREDENTIALS_FILE, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                
                with open(config.TOKEN_FILE, "w") as token:
                    token.write(self.creds.to_json())

            self.client = gspread.authorize(self.creds)
            self.is_authenticated = True
            return True
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False

    def connect_sheet(self):
        if not self.is_authenticated:
            if not self.authenticate():
                return False

        if config.SPREADSHEET_ID == 'YOUR_SPREADSHEET_ID_HERE':
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

if __name__ == "__main__":
    # simple test
    sm = SheetManager()
    if sm.authenticate():
        print("Auth successful")
    else:
        print("Auth failed")
