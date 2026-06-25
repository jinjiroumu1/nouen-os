import json
import streamlit as st


def _sheets_client():
    try:
        from google.oauth2.service_account import Credentials
        import gspread

        sa_json = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not sa_json:
            return None
        sa_info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(
            sa_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
        )
        return gspread.authorize(creds)
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
