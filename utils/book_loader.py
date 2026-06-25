import base64
import json
import streamlit as st


def _drive_service():
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        sa_json = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not sa_json:
            return None
        sa_info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        return build("drive", "v3", credentials=creds)
    except Exception:
        return None


@st.cache_data(ttl=1800)
def load_books() -> list[dict]:
    """
    Google DriveフォルダのPDFを全件取得してbase64エンコードで返す。
    返り値: [{"name": "ファイル名", "data": "base64文字列"}, ...]
    Google Drive未設定の場合は空リストを返す（フォールバック）。
    """
    folder_id = st.secrets.get("BOOK_FOLDER_ID", "")
    if not folder_id:
        return []

    service = _drive_service()
    if not service:
        return []

    try:
        from googleapiclient.http import MediaIoBaseDownload
        import io

        # フォルダ内のPDFを全件検索
        query = (
            f"'{folder_id}' in parents"
            " and mimeType='application/pdf'"
            " and trashed=false"
        )
        result = service.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=50,
        ).execute()
        files = result.get("files", [])

        books = []
        for f in files:
            try:
                request = service.files().get_media(fileId=f["id"])
                buf = io.BytesIO()
                downloader = MediaIoBaseDownload(buf, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
                books.append({"name": f["name"], "data": b64})
            except Exception:
                continue

        return books

    except Exception:
        return []
