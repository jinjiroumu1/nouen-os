"""
scripts/rename_invoices.py

Google Driveフォルダ内の納品書画像をClaude APIで読み取り、
「納品書_日付_仕入先_商品名_金額.jpg」形式にリネームするスクリプト。

使い方:
  python scripts/rename_invoices.py

必要な環境変数（.env または 環境変数に設定）:
  GOOGLE_SERVICE_ACCOUNT_JSON  サービスアカウントのJSONキー（文字列）
  ANTHROPIC_API_KEY            Claude APIキー

対象フォルダID（スクリプト内で固定）:
  1YSs51BO6PIeO6nzei7uuoJfCAQ99fOP8
"""

import base64
import io
import json
import os
import re
import sys
import time

FOLDER_ID = "1YSs51BO6PIeO6nzei7uuoJfCAQ99fOP8"
IMAGE_MIMES = {
    "image/jpeg": ".jpg",
    "image/png":  ".png",
    "image/gif":  ".gif",
    "image/webp": ".webp",
}


# ── Google Drive ──────────────────────────────────────────

def _drive_service():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        # ファイルパスとして試みる
        if os.path.exists("service_account.json"):
            with open("service_account.json") as f:
                sa_json = f.read()
        else:
            sys.exit("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON が未設定です。")
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    sa_info = json.loads(sa_json)
    creds = Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)


def list_images(service):
    mime_filter = " or ".join(f"mimeType='{m}'" for m in IMAGE_MIMES)
    query = f"'{FOLDER_ID}' in parents and ({mime_filter}) and trashed=false"
    result = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        pageSize=100,
    ).execute()
    return result.get("files", [])


def download_file(service, file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def rename_file(service, file_id: str, new_name: str):
    service.files().update(
        fileId=file_id,
        body={"name": new_name},
    ).execute()


# ── Claude API ────────────────────────────────────────────

def extract_info(image_bytes: bytes, mime_type: str) -> dict:
    """Claude APIで納品書から日付・仕入先・商品名・金額を抽出する。"""
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY が未設定です。")
    client = anthropic.Anthropic(api_key=api_key)

    b64 = base64.standard_b64encode(image_bytes).decode()
    prompt = """この納品書・請求書画像から以下の情報をJSONで抽出してください。
不明な項目は null にしてください。

{
  "date": "日付（YYYYMMDD形式、例: 20260621）",
  "supplier": "仕入先・会社名（例: 二見酒店）",
  "product": "主な商品名（例: A生樽20L）",
  "amount": "合計金額（数字のみ、例: 42000）"
}

JSONのみ返してください。"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    text = response.content[0].text
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        return json.loads(m.group())
    return {}


# ── ファイル名生成 ────────────────────────────────────────

def _sanitize(s: str) -> str:
    """ファイル名に使えない文字を除去する。"""
    if not s:
        return "不明"
    s = re.sub(r'[\\/:*?"<>|]', '', s)
    return s.strip()[:30]


def build_filename(info: dict, orig_mime: str) -> str:
    ext = IMAGE_MIMES.get(orig_mime, ".jpg")
    date     = _sanitize(info.get("date") or "日付不明")
    supplier = _sanitize(info.get("supplier") or "仕入先不明")
    product  = _sanitize(info.get("product") or "商品不明")
    amount   = info.get("amount")
    amount_str = f"{_sanitize(str(amount))}円" if amount else "金額不明"
    return f"納品書_{date}_{supplier}_{product}_{amount_str}{ext}"


# ── メイン ────────────────────────────────────────────────

def main():
    print("Google Driveに接続中...")
    service = _drive_service()

    print(f"フォルダ {FOLDER_ID} の画像を取得中...")
    files = list_images(service)
    if not files:
        print("画像ファイルが見つかりませんでした。")
        return

    print(f"{len(files)} 件の画像が見つかりました。\n")
    print(f"{'元のファイル名':<40} {'新しいファイル名'}")
    print("-" * 90)

    results = []
    for f in files:
        orig_name = f["name"]
        mime = f["mimeType"]
        try:
            image_bytes = download_file(service, f["id"])
            info = extract_info(image_bytes, mime)
            new_name = build_filename(info, mime)

            rename_file(service, f["id"], new_name)
            status = "✅ OK"
            results.append((orig_name, new_name, status))
            print(f"{orig_name:<40} → {new_name}  {status}")

            # API rate limit 対策
            time.sleep(1)

        except Exception as e:
            status = f"❌ ERROR: {e}"
            results.append((orig_name, "（変更なし）", status))
            print(f"{orig_name:<40} → {status}")

    print("\n完了しました。")
    ok_count = sum(1 for _, _, s in results if s.startswith("✅"))
    print(f"成功: {ok_count} / {len(files)} 件")


if __name__ == "__main__":
    main()
