import base64
import io
import json
import streamlit as st

SUPPORTED_MIME = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
]


def _drive_service(readonly: bool = True):
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        sa_json = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not sa_json:
            return None
        sa_info = json.loads(sa_json)
        scope = (
            "https://www.googleapis.com/auth/drive.readonly"
            if readonly
            else "https://www.googleapis.com/auth/drive"
        )
        creds = Credentials.from_service_account_info(sa_info, scopes=[scope])
        return build("drive", "v3", credentials=creds)
    except Exception:
        return None


@st.cache_data(ttl=1800)
def load_pop_files(folder_id: str = "") -> list[dict]:
    """
    指定フォルダ内のPDF・画像ファイルを全件取得してbase64エンコードで返す。
    folder_id が未指定の場合は Secrets の POP_FOLDER_ID を使う。
    """
    if not folder_id:
        folder_id = st.secrets.get("POP_FOLDER_ID", "")
    if not folder_id:
        return []

    service = _drive_service(readonly=True)
    if not service:
        return []

    try:
        from googleapiclient.http import MediaIoBaseDownload

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


def upload_pop_file(folder_id: str, file_name: str, file_bytes: bytes, mime_type: str) -> tuple[bool, str]:
    """
    指定フォルダにファイルをアップロードする。
    返り値: (成功フラグ, エラーメッセージ)
    """
    service = _drive_service(readonly=False)
    if not service:
        return False, "Google Drive サービスアカウントが設定されていません"

    try:
        from googleapiclient.http import MediaIoBaseUpload

        metadata = {"name": file_name, "parents": [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
        service.files().create(
            body=metadata,
            media_body=media,
            fields="id",
        ).execute()
        return True, ""
    except Exception as e:
        return False, str(e)
