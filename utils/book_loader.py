import base64
import json
import streamlit as st


def _drive_service():
    """Google Drive APIサービスを返す。Secretsにキーがなければ None。"""
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
def list_pdf_files() -> list[dict]:
    """
    BOOK_FOLDER_ID 配下の PDF ファイル一覧を返す。
    戻り値: [{"id": "...", "name": "..."}, ...]
    """
    folder_id = st.secrets.get("BOOK_FOLDER_ID", "")
    if not folder_id:
        return []
    service = _drive_service()
    if not service:
        return []
    try:
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
        return result.get("files", [])
    except Exception:
        return []


@st.cache_data(ttl=1800)
def load_pdf_as_base64(file_id: str) -> str:
    """Google DriveのPDFをダウンロードしてbase64文字列で返す。"""
    service = _drive_service()
    if not service:
        return ""
    try:
        from googleapiclient.http import MediaIoBaseDownload
        import io
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return ""


def get_pdf_document_blocks() -> list[dict]:
    """
    フォルダ内の全PDFをClaude APIのdocumentブロック形式で返す。
    PDFが取得できない場合は空リストを返す（フォールバック）。

    Claude API document block 形式:
    {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": "<base64文字列>"
        },
        "title": "ファイル名"
    }
    """
    files = list_pdf_files()
    blocks = []
    for f in files:
        b64 = load_pdf_as_base64(f["id"])
        if b64:
            blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
                "title": f["name"],
            })
    return blocks
