import base64
import json
import re
import streamlit as st
from datetime import datetime, timezone, timedelta


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


def _extract_year_month(text: str) -> tuple[int, int] | None:
    """文字列から年月を抽出する。例: '2025請求書', '2025_05', '202504' など。"""
    # YYYY-MM または YYYY_MM または YYYYMM または YYYY年MM月
    patterns = [
        r'(\d{4})[_\-年](\d{1,2})[月_\-]?',
        r'(\d{4})(\d{2})(?!\d)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            if 2000 <= year <= 2099 and 1 <= month <= 12:
                return year, month
    # 年のみ（YYYY）
    m = re.search(r'(\d{4})', text)
    if m:
        year = int(m.group(1))
        if 2000 <= year <= 2099:
            return year, None
    return None


def _is_recent(year: int, month: int | None, cutoff: datetime) -> bool:
    """年月が cutoff 以降かどうか判定する。月不明の場合は年で判定。"""
    if month is None:
        return year >= cutoff.year
    dt = datetime(year, month, 1, tzinfo=timezone.utc)
    return dt >= cutoff.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _list_pdfs_in_folder(service, folder_id: str) -> list[dict]:
    """指定フォルダ直下のPDFファイル一覧（id, name, modifiedTime）を返す。"""
    try:
        result = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
            fields="files(id, name, modifiedTime)",
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


def _should_include(file: dict, folder_name: str, cutoff: datetime) -> bool:
    """ファイル名・フォルダ名・更新日時で直近3ヶ月判定する。"""
    # ファイル名から年月を抽出
    ym = _extract_year_month(file["name"])
    if ym:
        return _is_recent(ym[0], ym[1], cutoff)

    # フォルダ名から年月を抽出
    ym = _extract_year_month(folder_name)
    if ym:
        return _is_recent(ym[0], ym[1], cutoff)

    # 更新日時で判定
    modified = file.get("modifiedTime", "")
    if modified:
        try:
            dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
            return dt >= cutoff
        except Exception:
            pass

    return True  # 判定不能な場合は含める


@st.cache_data(ttl=1800)
def load_invoices() -> list[dict]:
    """
    INVOICE_FOLDER_ID フォルダ内のPDFを再帰的（2段階）に取得。
    直近3ヶ月分に絞り込んでbase64エンコードで返す。
    返り値: [{"name": "ファイル名", "data": "base64文字列"}, ...]
    """
    folder_id = st.secrets.get("INVOICE_FOLDER_ID", "")
    if not folder_id:
        return []

    service = _drive_service()
    if not service:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    invoices = []

    # フォルダ直下のPDF
    for f in _list_pdfs_in_folder(service, folder_id):
        if _should_include(f, "", cutoff):
            b64 = _download_pdf(service, f["id"])
            if b64:
                invoices.append({"name": f["name"], "data": b64})

    # サブフォルダ内のPDF（1段階のみ）
    for subfolder in _list_subfolders(service, folder_id):
        for f in _list_pdfs_in_folder(service, subfolder["id"]):
            if _should_include(f, subfolder["name"], cutoff):
                b64 = _download_pdf(service, f["id"])
                if b64:
                    invoices.append({"name": f"{subfolder['name']}/{f['name']}", "data": b64})

    return invoices
