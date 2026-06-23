import streamlit as st
import pandas as pd
from datetime import date
from db.database import get_connection
from components.knowledge_card import knowledge_card
from utils.notion_sync import save_farm_diary
from utils.ai_advisor import get_ai_response, MAX_TURNS

st.set_page_config(page_title="農業日誌", page_icon="🌿", layout="wide")
st.title("🌿 農業日誌")
st.caption("共同体の記憶を記録する。天候・作業・気づきをここに。")

# ── セッション初期化 ───────────────────────────────────────
if "diary_entry" not in st.session_state:
    st.session_state.diary_entry = None   # 直近に保存した日誌
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []    # AIとのやり取り履歴
if "ai_responses" not in st.session_state:
    st.session_state.ai_responses = []    # 表示用（役割付き）

# ── 入力フォーム ──────────────────────────────────────────
with st.expander("📝 新しい日誌を書く", expanded=True):
    with st.form("diary_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_date = st.date_input("日付", value=date.today())
        with col2:
            weather = st.selectbox("天候", ["晴れ", "曇り", "雨", "雪", "その他"])
        with col3:
            crop = st.text_input("作物", placeholder="例：トマト、きゅうり")

        work_done    = st.text_area("作業内容", placeholder="今日やったこと")
        observation  = st.text_area("観察・気づき（創発知）", placeholder="現場で感じたこと・変化")
        question     = st.text_input("疑問・問い", placeholder="なぜ？どうして？")
        hypothesis   = st.text_area("仮説", placeholder="こうじゃないかな…")

        source_type = st.selectbox(
            "知識の種別",
            ["souhatsuchi", "kenjinchi", "kasanatta", "suuchi"],
            format_func=lambda x: {
                "souhatsuchi": "🌸 創発知",
                "kenjinchi":   "💙 賢人知",
                "kasanatta":   "💜 重なった知",
                "suuchi":      "🩶 数値データ",
            }[x],
        )

        submitted = st.form_submit_button("記録する")
        if submitted:
            conn = get_connection()
            conn.execute(
                """INSERT INTO farm_diary
                   (date, weather, crop, work_done, observation, question, hypothesis, source_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (str(entry_date), weather, crop, work_done, observation,
                 question, hypothesis, source_type),
            )
            conn.commit()
            conn.close()
            save_farm_diary(entry_date, weather, crop, work_done, observation,
                            question, hypothesis, source_type)

            # AI対話のリセット＆日誌を保存
            st.session_state.diary_entry = {
                "date":        str(entry_date),
                "weather":     weather,
                "crop":        crop,
                "work_done":   work_done,
                "observation": observation,
                "question":    question,
                "hypothesis":  hypothesis,
            }
            st.session_state.chat_history  = []
            st.session_state.ai_responses  = []

            # 1回目のAI返答を自動取得
            with st.spinner("AI勘ちゃんが考えています…"):
                reply = get_ai_response(st.session_state.diary_entry, [])
            st.session_state.ai_responses.append({"role": "assistant", "content": reply})
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.success("記録しました。（Notionにも同期）")
            st.rerun()

# ── AI勘ちゃんとの対話 ────────────────────────────────────
if st.session_state.diary_entry:
    st.markdown("---")
    st.subheader("🤝 AI勘ちゃんからのコメント")
    st.caption(f"作物：{st.session_state.diary_entry.get('crop','—')}　｜　最大{MAX_TURNS}回の対話")

    # 対話履歴の表示
    for msg in st.session_state.ai_responses:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="🌱"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user", avatar="👨‍🌾"):
                st.markdown(msg["content"])

    # ユーザーが返信できる回数を計算
    user_turns = sum(1 for m in st.session_state.chat_history if m["role"] == "user")

    if user_turns < MAX_TURNS - 1:
        user_input = st.chat_input(
            f"勘ちゃんへの返事・追加の問い（あと{MAX_TURNS - 1 - user_turns}回）"
        )
        if user_input:
            st.session_state.ai_responses.append({"role": "user", "content": user_input})
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            with st.spinner("勘ちゃんが考えています…"):
                reply = get_ai_response(
                    st.session_state.diary_entry,
                    st.session_state.chat_history,
                )
            st.session_state.ai_responses.append({"role": "assistant", "content": reply})
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.rerun()
    else:
        st.info("今日の対話はここまで。記録お疲れさまでした。育てる。食べる。学ぶ。循環する。🌱")

    if st.button("対話をリセットして新しい日誌へ"):
        st.session_state.diary_entry   = None
        st.session_state.chat_history  = []
        st.session_state.ai_responses  = []
        st.rerun()

# ── 過去の日誌一覧 ────────────────────────────────────────
st.markdown("---")
st.subheader("過去の日誌")

conn = get_connection()
rows = conn.execute("SELECT * FROM farm_diary ORDER BY date DESC, id DESC").fetchall()
conn.close()

if not rows:
    st.info("まだ日誌がありません。上のフォームから記録を始めましょう。")
else:
    search = st.text_input("🔍 絞り込み（作物・作業・気づき）")
    df = pd.DataFrame([dict(r) for r in rows])
    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        df = df[mask]

    for _, row in df.iterrows():
        title = f"{row['date']} ／ {row['weather']} ／ {row['crop'] or '—'}"
        body_parts = []
        if row.get("work_done"):
            body_parts.append(f"【作業】{row['work_done']}")
        if row.get("observation"):
            body_parts.append(f"【観察】{row['observation']}")
        if row.get("question"):
            body_parts.append(f"【疑問】{row['question']}")
        if row.get("hypothesis"):
            body_parts.append(f"【仮説】{row['hypothesis']}")
        knowledge_card(title, "\n".join(body_parts), row.get("source_type", "souhatsuchi"))
