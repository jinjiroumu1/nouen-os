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


def _list_pdfs_in_folder(service, folder_id: str) -> list[dict]:
    """指定フォルダ直下のPDFファイル一覧を返す。"""
    try:
        result = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
            fields="files(id, name)",
            pageSize=100,
        ).execute()
        return result.get("files", [])
    except Exception:
        return []


def _list_subfolders(service, folder_id: str) -> list[dict]:
    """指定フォルダ直下のサブフォルダ一覧を返す。"""
    try:
        result = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)",
            pageSize=50,
        ).execute()
        return result.get("files", [])
    except Exception:
        return []


def _download_pdf(service, file_id: str) -> str | None:
    """PDFをダウンロードしてbase64文字列で返す。失敗時はNone。"""
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
        return None


@st.cache_data(ttl=1800)
def load_invoices() -> list[dict]:
    """
    INVOICE_FOLDER_ID フォルダ内のPDFを再帰的（2段階）に取得してbase64エンコードで返す。
    フォルダ直下 + サブフォルダ直下のPDFを対象とする。
    返り値: [{"name": "ファイル名", "data": "base64文字列"}, ...]
    """
    folder_id = st.secrets.get("INVOICE_FOLDER_ID", "")
    if not folder_id:
        return []

    service = _drive_service()
    if not service:
        return []

    invoices = []

    # フォルダ直下のPDF
    for f in _list_pdfs_in_folder(service, folder_id):
        b64 = _download_pdf(service, f["id"])
        if b64:
            invoices.append({"name": f["name"], "data": b64})

    # サブフォルダ内のPDF（1段階のみ）
    for subfolder in _list_subfolders(service, folder_id):
        for f in _list_pdfs_in_folder(service, subfolder["id"]):
            b64 = _download_pdf(service, f["id"])
            if b64:
                invoices.append({"name": f"{subfolder['name']}/{f['name']}", "data": b64})

    return invoices
