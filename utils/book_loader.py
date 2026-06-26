import base64
import io
import json
import streamlit as st

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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


def _download_bytes(service, file_id: str) -> bytes | None:
    try:
        from googleapiclient.http import MediaIoBaseDownload
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
    except Exception:
        return None


def _docx_to_text(data: bytes) -> str:
    """python-docx でWordファイルからテキストを抽出する。"""
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""


@st.cache_data(ttl=1800)
def load_books() -> list[dict]:
    """
    Google DriveフォルダのPDF・Wordを全件取得して返す。
    返り値:
      PDF  → {"name": str, "type": "pdf",  "data": "base64文字列"}
      Word → {"name": str, "type": "word", "text": "抽出テキスト"}
    Drive未設定の場合は空リスト。
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
            f" and (mimeType='application/pdf' or mimeType='{DOCX_MIME}')"
            " and trashed=false"
        )
        result = service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            pageSize=50,
        ).execute()
        files = result.get("files", [])

        books = []
        for f in files:
            data = _download_bytes(service, f["id"])
            if not data:
                continue
            if f["mimeType"] == DOCX_MIME:
                text = _docx_to_text(data)
                if text:
                    books.append({"name": f["name"], "type": "word", "text": text})
            else:
                b64 = base64.standard_b64encode(data).decode("utf-8")
                books.append({"name": f["name"], "type": "pdf", "data": b64})

        return books

    except Exception:
        return []
