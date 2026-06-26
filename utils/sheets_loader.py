import json
import streamlit as st


def _sheets_client(write=False):
    try:
        from google.oauth2.service_account import Credentials
        import gspread

        sa_json = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not sa_json:
            return None
        sa_info = json.loads(sa_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ] if write else [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
        return gspread.authorize(creds)
    except Exception:
        return None


COST_SHEET_ID = "1-5qW6qNy7QX0dme8nypS5rjjO-2h2A033ys8XiGcwr4"


def append_cost_row(row: list) -> bool:
    """
    原価計算シートの末尾に1行追記する。
    row: [日付, 商品名, 農家さん名, 仕入価格, 送料, 全体の重さ, 1商品の重さ,
          原価, 販売価格, 粗利, 備考, 写真リンク]
    成功時 True、失敗時 False を返す。
    """
    client = _sheets_client(write=True)
    if not client:
        return False
    try:
        wb = client.open_by_key(COST_SHEET_ID)
        ws = wb.sheet1
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception:
        return False


def upload_delivery_photo(image_bytes: bytes, filename: str) -> str | None:
    """
    納品書画像を DELIVERY_PHOTO_FOLDER_ID に保存し、共有リンクを返す。
    失敗時は None を返す。
    """
    import json
    import io as _io
    folder_id = st.secrets.get("DELIVERY_PHOTO_FOLDER_ID", "")
    if not folder_id:
        return None
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload

        sa_json = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not sa_json:
            return None
        sa_info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        service = build("drive", "v3", credentials=creds)

        media = MediaIoBaseUpload(
            _io.BytesIO(image_bytes),
            mimetype="image/jpeg",
            resumable=False,
        )
        file_meta = {"name": filename, "parents": [folder_id]}
        uploaded = service.files().create(
            body=file_meta,
            media_body=media,
            fields="id",
        ).execute()
        file_id = uploaded.get("id")

        # 閲覧者権限を付与して共有リンクを生成
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

        return f"https://drive.google.com/file/d/{file_id}/view"
    except Exception:
        return None


def _sheet_to_text(client, sheet_id: str, label: str) -> str:
    """スプレッドシートの全シートをテキスト形式に変換する"""
    if not sheet_id or not client:
        return ""
    try:
        wb = client.open_by_key(sheet_id)
        parts = [f"【{label}】"]
        for ws in wb.worksheets():
            rows = ws.get_all_values()
            if not rows:
                continue
            parts.append(f"▼ {ws.title}")
            for row in rows[:50]:  # 最大50行
                line = " | ".join(str(c) for c in row if str(c).strip())
                if line:
                    parts.append(line)
        return "\n".join(parts)
    except Exception:
        return ""


@st.cache_data(ttl=1800)
def load_sheets() -> str:
    """
    4つのスプレッドシートを読み込んでテキストで返す。
    Secrets未設定のシートは空文字でスキップ。
    返り値: 全シート内容を結合したテキスト文字列
    """
    client = _sheets_client()
    if not client:
        return ""

    sections = []
    sheet_map = {
        "SHEET_COST":    "原価計算表",
        "SHEET_PANDA":   "パンダ広場用まとめ",
        "SHEET_IKIKI":   "いきいきてらす用まとめ",
        "SHEET_PAYMENT": "支払チェックシート",
    }
    for secret_key, label in sheet_map.items():
        sheet_id = st.secrets.get(secret_key, "")
        text = _sheet_to_text(client, sheet_id, label)
        if text:
            sections.append(text)

    return "\n\n".join(sections)
