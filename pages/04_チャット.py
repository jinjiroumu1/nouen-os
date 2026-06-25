import streamlit as st
from db.database import get_connection
from components.knowledge_card import knowledge_card
from utils.notion_sync import save_chat_log
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
        # SQLiteに保存（answerは後で）
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

        # Notionに保存
        save_chat_log(question, reply, related_topics, source_type)

        st.session_state.chat_responses.append({"role": "assistant", "content": reply})
        st.session_state.chat_hist.append({"role": "assistant", "content": reply})
        st.success("記録しました。（Notionにも同期）")
        st.rerun()

# ── AI対話 ────────────────────────────────────────────────
if st.session_state.chat_entry:
    st.markdown("---")
    st.subheader("🤝 AI勘ちゃんの返答")
    st.caption(f"問い：{st.session_state.chat_entry.get('question','')[:40]}…　｜　最大{MAX_TURNS}回の対話")

    for msg in st.session_state.chat_responses:
        avatar = "🌱" if msg["role"] == "assistant" else "👨‍🌾"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    user_turns = sum(1 for m in st.session_state.chat_hist if m["role"] == "user")
    if user_turns < MAX_TURNS - 1:
        user_input = st.chat_input(f"さらに深める・別の問い（あと{MAX_TURNS - 1 - user_turns}回）")
        if user_input:
            st.session_state.chat_responses.append({"role": "user", "content": user_input})
            st.session_state.chat_hist.append({"role": "user", "content": user_input})
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

# ── 対話記録一覧 ──────────────────────────────────────────
st.markdown("---")
st.subheader("対話の記録")

conn = get_connection()
rows = conn.execute("SELECT * FROM chat_logs ORDER BY id DESC").fetchall()
conn.close()

if not rows:
    st.info("まだ対話記録がありません。")
else:
    search = st.text_input("🔍 絞り込み")
    for row in rows:
        r = dict(row)
        if search and search not in str(r.values()):
            continue
        title = r["question"][:60] + ("…" if len(r["question"]) > 60 else "")
        parts = []
        if r.get("answer"):
            parts.append(f"【返答】{r['answer'][:200]}")
        if r.get("related_topics"):
            parts.append(f"【関連】{r['related_topics']}")
        parts.append(f"記録：{r.get('created_at', '')}")
        knowledge_card(title, "\n".join(parts), r.get("source_type", "souhatsuchi"))
