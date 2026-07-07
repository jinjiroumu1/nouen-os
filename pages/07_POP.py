import datetime
import io
import json
import streamlit as st
from pathlib import Path
from utils.notion_sync import save_pop_log, save_pop_record, load_pop_records, \
    save_oauth_token, load_oauth_token
from utils.ai_advisor import get_ai_response_chat

POP_DRIVE_FOLDER_ID = "1M0ktbjZ9Wj_XuHo5kJAxO5pSciC3QLfp"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

st.set_page_config(page_title="POP", page_icon="🪧", layout="wide")

_img = Path("docs/characters/pop.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)

st.title("🪧 POP")


# ── Google OAuth ヘルパー（PKCEなし・直接URLビルド方式） ──
def _oauth_config():
    """GOOGLE_OAUTH_JSON から client_id / client_secret / redirect_uri を取得する。"""
    raw = st.secrets.get("GOOGLE_OAUTH_JSON", "")
    if not raw:
        return None
    config = json.loads(raw)
    app_type = "web" if "web" in config else "installed"
    info = config[app_type]
    return {
        "client_id":     info["client_id"],
        "client_secret": info["client_secret"],
        "redirect_uri":  info["redirect_uris"][0],
    }


def _build_auth_url(cfg: dict) -> str:
    """PKCEなし・stateなしのシンプルな認証URLを構築する。"""
    import urllib.parse
    params = {
        "client_id":     cfg["client_id"],
        "redirect_uri":  cfg["redirect_uri"],
        "response_type": "code",
        "scope":         " ".join(DRIVE_SCOPES),
        "access_type":   "offline",
        "prompt":        "consent",
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)


def _refresh_access_token(cfg: dict, refresh_token: str) -> dict | None:
    """refresh_token で新しい access_token を取得して返す。失敗時は None。"""
    import requests as _req
    try:
        resp = _req.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "refresh_token": refresh_token,
                "grant_type":    "refresh_token",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _load_and_restore_token():
    """
    Notionからトークンを読み込み、有効ならsession_stateに復元する。
    期限切れの場合はrefresh_tokenで更新してNotionにも保存する。
    """
    if "google_oauth_creds" in st.session_state:
        return  # 既に復元済み

    cfg = _oauth_config()
    if not cfg:
        return

    tok = load_oauth_token("gdrive")
    if not tok or not tok.get("access_token"):
        return

    # 有効期限チェック
    expiry_str = tok.get("expiry", "")
    is_expired = True
    if expiry_str:
        try:
            from datetime import timezone as _tz
            expiry_dt = datetime.datetime.fromisoformat(expiry_str)
            is_expired = expiry_dt <= datetime.datetime.now(tz=_tz.utc)
        except Exception:
            is_expired = True

    if is_expired and tok.get("refresh_token"):
        # リフレッシュ
        new_tok = _refresh_access_token(cfg, tok["refresh_token"])
        if not new_tok:
            return
        import time as _time
        expiry_dt = datetime.datetime.fromtimestamp(
            _time.time() + new_tok.get("expires_in", 3600),
            tz=datetime.timezone.utc,
        )
        access_token  = new_tok["access_token"]
        refresh_token = new_tok.get("refresh_token") or tok["refresh_token"]
        expiry        = expiry_dt.isoformat()
        save_oauth_token("gdrive", access_token, refresh_token, expiry)
    elif is_expired:
        return  # リフレッシュトークンもなければ再認証が必要
    else:
        access_token  = tok["access_token"]
        refresh_token = tok.get("refresh_token", "")

    st.session_state["google_oauth_creds"] = {
        "token":         access_token,
        "refresh_token": refresh_token,
        "token_uri":     "https://oauth2.googleapis.com/token",
        "client_id":     cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "scopes":        ["https://www.googleapis.com/auth/drive.file"],
    }


def _get_drive_service():
    creds_dict = st.session_state.get("google_oauth_creds")
    if not creds_dict:
        return None
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials(
            token=creds_dict["token"],
            refresh_token=creds_dict.get("refresh_token"),
            token_uri=creds_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_dict["client_id"],
            client_secret=creds_dict["client_secret"],
            scopes=creds_dict.get("scopes"),
        )
        return build("drive", "v3", credentials=creds)
    except Exception:
        return None


def _upload_to_drive(file_name: str, file_bytes: bytes, mime_type: str) -> tuple[bool, str]:
    service = _get_drive_service()
    if not service:
        return False, "Googleドライブに未認証です"
    try:
        from googleapiclient.http import MediaIoBaseUpload
        metadata = {"name": file_name, "parents": [POP_DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=metadata, media_body=media, fields="id").execute()
        return True, ""
    except Exception as e:
        return False, str(e)


# 起動時にNotionからトークンを復元（session_stateが空でも認証済み状態を維持）
_load_and_restore_token()

tab_ask, tab_save = st.tabs(["💬 質問する", "💾 保存する"])

# ── 質問するタブ ──────────────────────────────────────────
with tab_ask:
    st.caption("POP記録DBを検索し、AI勘ちゃんに質問する")

    with st.spinner("POP記録を読み込み中…"):
        pop_records = load_pop_records(limit=100)

    st.subheader("📋 POP記録一覧")

    with st.form("pop_search_form"):
        fc1, fc2, fc3, fc4 = st.columns([3, 3, 2, 1])
        with fc1:
            q_name = st.text_input("商品名", placeholder="例：しょうが")
        with fc2:
            q_keyword = st.text_input("キーワード", placeholder="例：夏")
        with fc3:
            q_category = st.selectbox("区分",
                                      ["すべて", "野菜", "農家", "値札", "イベント", "カフェメニュー"])
        with fc4:
            st.markdown("<br>", unsafe_allow_html=True)
            searched = st.form_submit_button("🔍 検索する")

    if not searched:
        results = pop_records
    else:
        results = pop_records
        if q_name:
            results = [r for r in results if q_name.lower() in r["product_name"].lower()]
        if q_keyword:
            results = [r for r in results if q_keyword.lower() in r["keyword"].lower()]
        if q_category != "すべて":
            results = [r for r in results if r["category"] == q_category]

    if not pop_records:
        st.info("POP記録がまだありません。「保存する」タブから登録してください。")
    else:
        st.caption(f"{len(results)} 件 / 全 {len(pop_records)} 件")
        st.markdown("---")

        h1, h2, h3, h4, h5 = st.columns([3, 3, 2, 2, 1])
        h1.caption("**商品名**")
        h2.caption("**キーワード**")
        h3.caption("**区分**")
        h4.caption("**登録日**")
        h5.caption("**リンク**")

        for r in results:
            c1, c2, c3, c4, c5 = st.columns([3, 3, 2, 2, 1])
            c1.write(r["product_name"] or "—")
            c2.write(r["keyword"] or "—")
            c3.write(r["category"] or "—")
            c4.write(r["registered_date"] or "—")
            if r["page_url"]:
                c5.markdown(f"[開く]({r['page_url']})")

    st.markdown("---")

    st.subheader("💬 AI勘ちゃんに質問する")
    st.caption("POPの文言・キャッチコピーのアイデアなど、何でも聞いてください。")

    if "pop_chat" not in st.session_state:
        st.session_state.pop_chat = []

    for msg in st.session_state.pop_chat:
        avatar = "👨‍🌾" if msg["role"] == "user" else "🌱"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    user_input = st.chat_input("例：しょうがのPOPのキャッチコピーを考えて")
    if user_input:
        st.session_state.pop_chat.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👨‍🌾"):
            st.markdown(user_input)

        pop_context = ""
        if pop_records:
            lines = [
                f"・{r['product_name']} [{r['category']}] キーワード:{r['keyword']} 登録日:{r['registered_date']}"
                for r in pop_records[:30]
            ]
            pop_context = "\n".join(lines)

        with st.spinner("勘ちゃんが考えています…"):
            reply = get_ai_response_chat(
                {
                    "question": user_input,
                    "related_topics": f"POP・キャッチコピー\n\n【登録済みPOP一覧】\n{pop_context}",
                },
                st.session_state.pop_chat[:-1],
            )

        st.session_state.pop_chat.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant", avatar="🌱"):
            st.markdown(reply)
        save_pop_log(user_input, reply)

    if st.session_state.pop_chat and st.button("チャットをリセット"):
        st.session_state.pop_chat = []
        st.rerun()

# ── 保存するタブ ──────────────────────────────────────────
with tab_save:
    st.caption("POPデータをGoogleドライブ＋Notionに保存する")

    # 「200MB per file」表示を非表示
    st.markdown(
        "<style>small.st-emotion-cache-7oyrr6, "
        "[data-testid='stFileUploaderDropzoneInstructions'] small { display:none !important; }</style>",
        unsafe_allow_html=True,
    )

    # ── Google認証状態の表示・認証ボタン ──────────────────
    is_authenticated = "google_oauth_creds" in st.session_state
    if is_authenticated:
        st.success("✅ Googleドライブに接続済み")
        if st.button("🔓 ログアウト", key="gdrive_logout"):
            st.session_state.pop("google_oauth_creds", None)
            st.rerun()
    else:
        _cfg = _oauth_config()
        if _cfg:
            _auth_url = _build_auth_url(_cfg)
            st.info("Googleドライブへのアップロードには認証が必要です。")
            st.link_button("🔑 Googleアカウントで認証する", _auth_url)
        else:
            st.warning("GOOGLE_OAUTH_JSON が設定されていません。")

    st.markdown("---")

    with st.form("pop_upload_form", clear_on_submit=True):
        product_name = st.text_input("商品名", placeholder="例：しょうが")
        keyword      = st.text_input("キーワード", placeholder="例：夏　辛い　ジンジャー")
        category     = st.radio("区分", ["野菜", "農家", "値札", "イベント", "カフェメニュー"],
                                horizontal=True)
        uploaded     = st.file_uploader("POPデータ（画像・PDF・PPTX）",
                                        type=["png", "jpg", "jpeg", "gif", "webp", "pdf", "pptx"])
        submitted    = st.form_submit_button("💾 保存する", disabled=not is_authenticated)

    if submitted:
        if not product_name:
            st.error("商品名を入力してください。")
        elif not uploaded:
            st.error("ファイルをアップロードしてください。")
        else:
            today      = datetime.date.today().strftime("%Y%m%d")
            ext        = uploaded.name.rsplit(".", 1)[-1]
            fname      = f"{category}_{product_name}_{keyword}_{today}.{ext}"
            file_bytes = uploaded.read()

            # 1. Google Driveにアップロード
            with st.spinner("Googleドライブにアップロード中…"):
                drive_ok, drive_err = _upload_to_drive(fname, file_bytes, uploaded.type)

            if not drive_ok:
                st.error(f"Driveへのアップロードに失敗しました：{drive_err}")
            else:
                # 2. Notionにメタデータ保存（ファイルはDriveに保存済みのためNoneで渡す）
                with st.spinner("Notionにメタデータを保存中…"):
                    ok, msg = save_pop_record(
                        product_name=product_name,
                        keyword=keyword,
                        category=category,
                        file_name=fname,
                        file_bytes=None,
                        mime_type=uploaded.type,
                    )
                if ok:
                    if msg and "失敗" in msg:
                        st.warning(f"⚠️ Driveへの保存は完了しました。Notionの記録に問題：{msg}")
                    elif msg:
                        st.success(f"✅ {msg}（Drive＋Notion）：{fname}")
                    else:
                        st.success(f"✅ 保存しました（Drive＋Notion）：{fname}")
                    st.cache_data.clear()
                else:
                    st.warning(f"⚠️ Driveへの保存は完了しました。Notionの記録に失敗：{msg}")
