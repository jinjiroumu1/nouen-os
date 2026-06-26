import base64
import json
import streamlit as st

# PDF・画像のMIMEタイプ
SUPPORTED_MIME = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
]


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
def load_pop_files() -> list[dict]:
    """
    POP_FOLDER_ID フォルダ内のPDF・画像ファイルを全件取得してbase64エンコードで返す。
    返り値: [{"name": str, "mime": str, "data": str}, ...]
    未設定の場合は空リストを返す。
    """
    folder_id = st.secrets.get("POP_FOLDER_ID", "")
    if not folder_id:
        return []

    service = _drive_service()
    if not service:
        return []

    try:
        from googleapiclient.http import MediaIoBaseDownload
        import io

        mime_filter = " or ".join(f"mimeType='{m}'" for m in SUPPORTED_MIME)
        query = f"'{folder_id}' in parents and ({mime_filter}) and trashed=false"
        result = service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            pageSize=100,
        ).execute()
        files = result.get("files", [])

        pop_files = []
        for f in files:
            try:
                request = service.files().get_media(fileId=f["id"])
                buf = io.BytesIO()
                downloader = MediaIoBaseDownload(buf, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
                pop_files.append({
                    "name": f["name"],
                    "mime": f["mimeType"],
                    "data": b64,
                })
            except Exception:
                continue

        return pop_files

    except Exception:
        return []
