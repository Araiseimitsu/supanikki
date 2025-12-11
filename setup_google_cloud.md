# Supanikki (超日記) Google Cloud セットアップガイド

SupanikkiがあなたのGoogleスプレッドシートに書き込むためには、Google Cloudの設定を行い、認証ファイルを取得する必要があります。以下の手順に従って `credentials.json` を取得してください。

1. **Google Cloud Console にアクセス**:
    [https://console.cloud.google.com/](https://console.cloud.google.com/) にアクセスします。

2. **新規プロジェクトの作成**:
    左上のプロジェクト選択ドロップダウンをクリックし、「新しいプロジェクト」を選択します。プロジェクト名（例: `Supanikki`）を入力して作成します。

3. **Google Sheets API の有効化**:
    * 上部の検索バーに「Google Sheets API」と入力します。
    * 検索結果から「Google Sheets API」を選択します。
    * **有効にする** をクリックします。

4. **Google Drive API の有効化**（ファイルアップロードを使う場合）:
    * 上部の検索バーに「Google Drive API」と入力します。
    * 検索結果から「Google Drive API」を選択します。
    * **有効にする** をクリックします。

5. **OAuth 同意画面の設定**:
    * メニューから「API とサービス」 > 「OAuth 同意画面」に移動します。
    * **外部** を選択し（Google Workspace組織がない場合）、**作成** をクリックします。
    * 「アプリ名」（例: Supanikki）と「ユーザーサポートメール」を入力します。
    * ページ下部の「デベロッパーの連絡先情報」を入力します。
    * **保存して次へ** をクリックします。
    * **スコープ**: このステップはスキップするか、`../auth/spreadsheets` を追加しても構いません。スキップしても後で要求されます。
    * **テストユーザー**: **重要**: あなた自身のGoogleメールアドレスを「テストユーザー」として追加してください。これを行わないと、認証時にエラー（アクセスブロック）が発生します。
    * **保存して次へ** をクリックして完了させます。

6. **認証情報の作成**:
    * メニューから「API とサービス」 > 「認証情報」に移動します。
    * 上部の **認証情報を作成** > **OAuth クライアント ID** をクリックします。
    * **アプリケーションの種類**: **デスクトップ アプリ** を選択します。
    * 名前: `Supanikki Desktop` など。
    * **作成** をクリックします。

7. **認証情報のダウンロード**:
    * 「OAuth クライアントを作成しました」というポップアップが表示されます。
    * **JSON をダウンロード** ボタンをクリックします。
    * ダウンロードしたファイルを `credentials.json` という名前に変更し、`supanikki` フォルダに保存します:
        `c:/Users/winni/my_projects/1/supanikki/credentials.json`

8. **スプレッドシートIDの取得**:
    * ログを保存したいGoogleスプレッドシートを新規作成するか、既存のものを開きます。
    * ブラウザのURLを確認してください: `https://docs.google.com/spreadsheets/d/abc123456789/edit...`
    * `/d/` と `/edit` の間にある文字列（上記の例では `abc123456789`）をコピーします。これがスプレッドシートIDです。
    * このIDを `config.py` ファイルの `SPREADSHEET_ID` の部分に貼り付けてください。

9. **DriveフォルダIDの設定（任意）**:
    * アップロード先フォルダを指定したい場合、Google Drive のフォルダURLを開きます:
      `https://drive.google.com/drive/folders/<FOLDER_ID>`
    * `<FOLDER_ID>` を `config.py` の `DRIVE_FOLDER_ID` に設定します。
      - ※ `DRIVE_FOLDER_ID` には **URLではなくIDのみ** を入れてください（`?usp=...` などは不要）
    * 空文字のままの場合は、マイドライブ直下へアップロードされます。

## 注意（Drive機能を追加した場合）

- **既存の `token.json` は再認証が必要な場合があります**:
  - Drive用スコープを追加すると、以前のトークンに権限が含まれないことがあります。
  - その場合は `token.json` を削除して再起動し、ブラウザで再認証してください。
- **共有リンクは作りません（自分のみ閲覧）**:
  - アップロード後のファイルは権限を変更しないため、既定で「自分のみ」閲覧です。
  - メッセージに記載されるURLも、他人が開いても権限がなければ閲覧できません。

## トラブルシューティング

### エラー 403: Google Sheets API has not been used

このエラーが出る場合、Google Cloud Projectで **Google Sheets API** が有効化されていません。
以下のリンクから有効化してください（エラーログに表示されたリンクと同じです）:
<https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1057775524808>
※ URLの末尾の数字はあなたのプロジェクトIDによって異なる場合がありますが、エラーメッセージ内のURLをクリックするのが確実です。

### エラー 403: access_denied

もし認証時に `access_denied` エラーが出る場合、**手順4の「テストユーザー」の設定**が完了していません。

1. Google Cloud Console で「OAuth 同意画面」を開きます。
2. 「テストユーザー」の欄を確認します。
3. `+ ADD USERS` ボタンを押し、あなたのGmailアドレスを入力して保存してください。
