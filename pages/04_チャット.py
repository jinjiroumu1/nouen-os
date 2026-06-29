import streamlit as st
from db.database import get_connection
from utils.notion_sync import save_chat_log, load_chat_logs
from utils.ai_advisor import get_ai_response_chat, MAX_TURNS

st.set_page_config(page_title="チャット", page_icon="💬", layout="wide")
from pathlib import Path as _P
_img = _P("docs/characters/otogi.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)
st.title("💬 チャット（AI−勘ちゃん）")
st.caption("日々の疑問を投げかける。基本書→賢人→農縁団の記録から一緒に考える。")

if "chat_entry" not in st.session_state:
    st.session_state.chat_entry = None
if "chat_hist" not in st.session_state:
    st.session_state.chat_hist = []
if "chat_responses" not in st.session_state:
    st.session_state.chat_responses = []

# ── 質問フォーム ───────────────────────────────────────────
with st.form("chat_form"):
    question       = st.text_area("疑問・問い", placeholder="例：なぜトマトの葉が黄色くなるの？")
    related_topics = st.text_input("関連トピック", placeholder="例：病害虫、土壌、トマト")
    source_type    = st.selectbox(
        "知識の種別",
        ["souhatsuchi", "kenjinchi", "kasanatta"],
        format_func=lambda x: {"souhatsuchi": "🌸 創発知", "kenjinchi": "💙 賢人知",
                               "kasanatta": "💜 重なった知"}[x],
    )
    submitted = st.form_submit_button("勘ちゃんに聞く")
    if submitted and question:
        conn = get_connection()
        conn.execute(
            """INSERT INTO chat_logs (question, answer, related_topics, source_type)
               VALUES (?,?,?,?)""",
            (question, "", related_topics, source_type),
        )
        conn.commit()
        conn.close()

        st.session_state.chat_entry = {
            "question": question,
            "related_topics": related_topics,
        }
        st.session_state.chat_hist      = []
        st.session_state.chat_responses = []

        with st.spinner("AI勘ちゃんが考えています…"):
            reply = get_ai_response_chat(st.session_state.chat_entry, [])

        save_chat_log(question, reply, related_topics, source_type)

        st.session_state.chat_responses.append({"role": "assistant", "content": reply})
        st.session_state.chat_hist.append({"role": "assistant", "content": reply})
        st.rerun()

# ── 最新の回答を入力欄のすぐ下に表示 ─────────────────────
if st.session_state.chat_entry and st.session_state.chat_responses:
    st.markdown("---")
    latest = st.session_state.chat_responses[-1]
    st.info(f"**👨‍💼 問い：** {st.session_state.chat_entry.get('question', '')}")
    st.success(f"**🌱 勘ちゃん：** {latest['content']}")

    # 続けて深める
    user_turns = sum(1 for m in st.session_state.chat_hist if m["role"] == "user")
    if user_turns < MAX_TURNS - 1:
        col_in, col_btn = st.columns([5, 1])
        with col_in:
            follow_up = st.text_input(
                "さらに深める",
                placeholder=f"さらに深める・別の問い（あと{MAX_TURNS - 1 - user_turns}回）",
                label_visibility="collapsed",
                key="chat_followup",
            )
        with col_btn:
            send_follow = st.button("送信", use_container_width=True, key="chat_followup_btn")
        if send_follow and follow_up:
            st.session_state.chat_responses.append({"role": "user", "content": follow_up})
            st.session_state.chat_hist.append({"role": "user", "content": follow_up})
            with st.spinner("勘ちゃんが考えています…"):
                reply = get_ai_response_chat(
                    st.session_state.chat_entry, st.session_state.chat_hist)
            st.session_state.chat_responses.append({"role": "assistant", "content": reply})
            st.session_state.chat_hist.append({"role": "assistant", "content": reply})
            st.rerun()
    else:
        st.info("今日の対話はここまで。学ぶ。循環する。🌱")

    if st.button("新しい問いへ"):
        st.session_state.chat_entry     = None
        st.session_state.chat_hist      = []
        st.session_state.chat_responses = []
        st.rerun()

# ── 過去の対話記録（Notionから） ──────────────────────────
st.markdown("---")
st.subheader("📚 過去の質問")

notion_logs = load_chat_logs(limit=30)

if not notion_logs:
    st.caption("まだ対話記録がありません。")
else:
    search = st.text_input("🔍 絞り込み", placeholder="キーワードで絞り込む", key="chat_search")
    for log in notion_logs:
        if search and search not in log["question"] and search not in log.get("answer", ""):
            continue
        label = {
            "🌸 創発知": "🌸", "💙 賢人知": "💙", "💜 重なった知": "💜"
        }.get(log.get("source_type", ""), "💬")
        title = f"{label} {log['question'][:60]}{'…' if len(log['question']) > 60 else ''}"
        with st.expander(title, expanded=False):
            if log.get("answer"):
                st.success(f"**🌱 勘ちゃん：** {log['answer']}")
            if log.get("related_topics"):
                st.caption(f"関連トピック：{log['related_topics']}")
