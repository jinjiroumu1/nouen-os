import base64
import datetime
import streamlit as st
from pathlib import Path
from utils.pop_loader import load_pop_files, upload_pop_file
from utils.notion_sync import save_pop_log
from utils.ai_advisor import get_ai_response_chat

POP_FOLDER_ID = "1M0ktbjZ9Wj_XuHo5kJAxO5pSciC3QLfp"

st.set_page_config(page_title="POP", page_icon="🪧", layout="wide")

_img = Path("docs/characters/pop.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)

st.title("🪧 POP")

tab_ask, tab_save = st.tabs(["💬 質問する", "💾 保存する"])

# ── 質問するタブ ──────────────────────────────────────────
with tab_ask:
    st.caption("商品POPをGoogle Driveから検索・ダウンロードする")

    with st.spinner("Google DriveからPOPファイルを読み込み中…"):
        files = load_pop_files(POP_FOLDER_ID)

    if not files:
        st.info(
            "POPファイルが見つかりません。\n"
            "Google Drive フォルダをサービスアカウントと共有してください。\n\n"
            "サービスアカウント: `nouen-os-drive@electric-wave-500502-n2.iam.gserviceaccount.com`"
        )
    else:
        st.success(f"{len(files)} 件のPOPファイルを読み込みました")

        query = st.text_input("🔍 商品名で検索", placeholder="例：しょうが　なす　ジンジャー")
        results = [f for f in files if query.lower() in f["name"].lower()] if query else files

        st.markdown(f"**{len(results)} 件**")
        st.markdown("---")

        for f in results:
            col_name, col_dl = st.columns([5, 1])
            with col_name:
                if f["mime"].startswith("image/"):
                    with st.expander(f"🖼️ {f['name']}"):
                        img_bytes = base64.b64decode(f["data"])
                        st.image(img_bytes, use_container_width=True)
                else:
                    st.markdown(f"📄 **{f['name']}**")
            with col_dl:
                st.download_button(
                    label="⬇️",
                    data=base64.b64decode(f["data"]),
                    file_name=f["name"],
                    mime=f["mime"],
                    key=f"dl_{f['name']}",
                )

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

        with st.spinner("勘ちゃんが考えています…"):
            reply = get_ai_response_chat(
                {"question": user_input, "related_topics": "POP・キャッチコピー"},
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
    st.caption("POPデータをGoogle Driveに保存する")

    with st.form("pop_upload_form", clear_on_submit=True):
        product_name = st.text_input("商品名", placeholder="例：しょうが")
        keyword      = st.text_input("キーワード", placeholder="例：夏　辛い　ジンジャー")
        category     = st.selectbox("区分", ["野菜", "農家", "値札", "イベント", "カフェメニュー"])
        uploaded     = st.file_uploader("POPデータ（画像またはPDF）",
                                        type=["png", "jpg", "jpeg", "gif", "webp", "pdf"])
        submitted    = st.form_submit_button("💾 保存する")

    if submitted:
        if not product_name:
            st.error("商品名を入力してください。")
        elif not uploaded:
            st.error("ファイルをアップロードしてください。")
        else:
            today = datetime.date.today().strftime("%Y%m%d")
            ext   = uploaded.name.rsplit(".", 1)[-1]
            fname = f"{category}_{product_name}_{keyword}_{today}.{ext}"
            file_bytes = uploaded.read()
            with st.spinner("Google Driveに保存中…"):
                ok, err = upload_pop_file(POP_FOLDER_ID, fname, file_bytes, uploaded.type)
            if ok:
                st.success(f"✅ 保存しました：{fname}")
                st.cache_data.clear()
            else:
                st.error(f"保存に失敗しました：{err}")
