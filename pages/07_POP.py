import datetime
import streamlit as st
from pathlib import Path
from utils.notion_sync import save_pop_log, save_pop_record, load_pop_records
from utils.ai_advisor import get_ai_response_chat

st.set_page_config(page_title="POP", page_icon="🪧", layout="wide")

_img = Path("docs/characters/pop.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)

st.title("🪧 POP")

tab_ask, tab_save = st.tabs(["💬 質問する", "💾 保存する"])

# ── 質問するタブ ──────────────────────────────────────────
with tab_ask:
    st.caption("POP記録DBを検索し、AI勘ちゃんに質問する")

    # POP記録一覧
    with st.spinner("POP記録を読み込み中…"):
        pop_records = load_pop_records(limit=100)

    st.subheader("📋 POP記録一覧")

    # 検索フィルター
    fc1, fc2, fc3 = st.columns([3, 3, 2])
    with fc1:
        q_name = st.text_input("商品名で検索", placeholder="例：しょうが")
    with fc2:
        q_keyword = st.text_input("キーワードで検索", placeholder="例：夏")
    with fc3:
        q_category = st.selectbox("区分で絞り込み",
                                  ["すべて", "野菜", "農家", "値札", "イベント", "カフェメニュー"])

    # フィルタリング
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

        # ヘッダー行
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

    # AI勘ちゃんチャット
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

        # POP記録をコンテキストに追加
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
    st.caption("POPデータをNotionに保存する")

    with st.form("pop_upload_form", clear_on_submit=True):
        product_name = st.text_input("商品名", placeholder="例：しょうが")
        keyword      = st.text_input("キーワード", placeholder="例：夏　辛い　ジンジャー")
        category     = st.radio("区分", ["野菜", "農家", "値札", "イベント", "カフェメニュー"],
                                horizontal=True)
        uploaded     = st.file_uploader("POPデータ（画像またはPDF）",
                                        type=["png", "jpg", "jpeg", "gif", "webp", "pdf"])
        submitted    = st.form_submit_button("💾 保存する")

    if submitted:
        if not product_name:
            st.error("商品名を入力してください。")
        elif not uploaded:
            st.error("ファイルをアップロードしてください。")
        else:
            today  = datetime.date.today().strftime("%Y%m%d")
            ext    = uploaded.name.rsplit(".", 1)[-1]
            fname  = f"{category}_{product_name}_{keyword}_{today}.{ext}"
            file_bytes = uploaded.read()
            with st.spinner("Notionに保存中…"):
                ok, msg = save_pop_record(
                    product_name=product_name,
                    keyword=keyword,
                    category=category,
                    file_name=fname,
                    file_bytes=file_bytes,
                    mime_type=uploaded.type,
                )
            if ok:
                if msg:
                    st.warning(f"⚠️ {msg}")
                else:
                    st.success(f"✅ 保存しました：{fname}")
                    st.cache_data.clear()
            else:
                st.error(f"保存に失敗しました：{msg}")
