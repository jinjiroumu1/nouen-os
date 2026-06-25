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
            return None, "GOOGLE_SERVICE_ACCOUNT_JSON が未設定"
        sa_info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        return build("drive", "v3", credentials=creds), None
    except Exception as e:
        return None, f"Drive認証エラー: {e}"


def _extract_year_month(text: str) -> tuple[int, int] | None:
    """文字列から年月を抽出する。"""
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
    m = re.search(r'(\d{4})', text)
    if m:
        year = int(m.group(1))
        if 2000 <= year <= 2099:
            return year, None
    return None


def _is_recent(year: int, month: int | None, cutoff: datetime) -> bool:
    if month is None:
        return year >= cutoff.year
    dt = datetime(year, month, 1, tzinfo=timezone.utc)
    return dt >= cutoff.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _list_pdfs_in_folder(service, folder_id: str) -> list[dict]:
    try:
        result = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
            fields="files(id, name, modifiedTime)",
            pageSize=100,
        ).execute()
        return result.get("files", [])
    except Exception as e:
        return []


def _list_subfolders(service, folder_id: str) -> list[dict]:
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


def _should_include(file: dict, folder_name: str, cutoff: datetime) -> tuple[bool, str]:
    """直近3ヶ月判定。(含める?, 判定理由) を返す。"""
    ym = _extract_year_month(file["name"])
    if ym:
        result = _is_recent(ym[0], ym[1], cutoff)
        return result, f"ファイル名から {ym[0]}/{ym[1]} を抽出"

    ym = _extract_year_month(folder_name)
    if ym:
        result = _is_recent(ym[0], ym[1], cutoff)
        return result, f"フォルダ名から {ym[0]}/{ym[1]} を抽出"

    modified = file.get("modifiedTime", "")
    if modified:
        try:
            dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
            result = dt >= cutoff
            return result, f"更新日時 {modified[:10]} で判定"
        except Exception:
            pass

    return True, "判定不能のため含める"


@st.cache_data(ttl=1800)
def load_invoices() -> tuple[list[dict], list[str]]:
    """
    INVOICE_FOLDER_ID フォルダ内のPDFを再帰的（2段階）に取得。
    直近3ヶ月分に絞り込んでbase64エンコードで返す。
    返り値: (invoices, debug_lines)
    """
    debug = []
    folder_id = st.secrets.get("INVOICE_FOLDER_ID", "")
    if not folder_id:
        return [], ["INVOICE_FOLDER_ID が未設定です"]

    debug.append(f"INVOICE_FOLDER_ID: {folder_id}")

    service, err = _drive_service()
    if not service:
        return [], [err]

    debug.append("Drive認証: OK")
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    debug.append(f"直近3ヶ月の基準日: {cutoff.date()}")

    invoices = []

    # フォルダ直下のPDF
    root_pdfs = _list_pdfs_in_folder(service, folder_id)
    debug.append(f"フォルダ直下のPDF: {len(root_pdfs)} 件")
    for f in root_pdfs:
        include, reason = _should_include(f, "", cutoff)
        debug.append(f"  {'✅' if include else '⏭️'} {f['name']} ({reason})")
        if include:
            b64 = _download_pdf(service, f["id"])
            if b64:
                invoices.append({"name": f["name"], "data": b64})
            else:
                debug.append(f"    ⚠️ ダウンロード失敗")

    # サブフォルダ
    subfolders = _list_subfolders(service, folder_id)
    debug.append(f"サブフォルダ: {len(subfolders)} 件 → {[s['name'] for s in subfolders]}")
    for subfolder in subfolders:
        sub_pdfs = _list_pdfs_in_folder(service, subfolder["id"])
        debug.append(f"  [{subfolder['name']}] PDF: {len(sub_pdfs)} 件")
        for f in sub_pdfs:
            include, reason = _should_include(f, subfolder["name"], cutoff)
            debug.append(f"    {'✅' if include else '⏭️'} {f['name']} ({reason})")
            if include:
                b64 = _download_pdf(service, f["id"])
                if b64:
                    invoices.append({"name": f"{subfolder['name']}/{f['name']}", "data": b64})
                else:
                    debug.append(f"      ⚠️ ダウンロード失敗")

    debug.append(f"取得完了: {len(invoices)} 件")
    return invoices, debug
