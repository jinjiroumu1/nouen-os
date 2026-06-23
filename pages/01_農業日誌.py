import streamlit as st
import pandas as pd
from datetime import date
from db.database import get_connection
from components.knowledge_card import knowledge_card
from utils.notion_sync import save_farm_diary

st.set_page_config(page_title="農業日誌", page_icon="🌿", layout="wide")
st.title("🌿 農業日誌")
st.caption("共同体の記憶を記録する。天候・作業・気づきをここに。")

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

        work_done = st.text_area("作業内容", placeholder="今日やったこと")
        observation = st.text_area("観察・気づき（創発知）", placeholder="現場で感じたこと・変化")
        question = st.text_input("疑問・問い", placeholder="なぜ？どうして？")
        hypothesis = st.text_area("仮説", placeholder="こうじゃないかな…")

        source_type = st.selectbox(
            "知識の種別",
            ["souhatsuchi", "kenjinchi", "kasanatta", "suuchi"],
            format_func=lambda x: {"souhatsuchi": "🌸 創発知", "kenjinchi": "💙 賢人知",
                                   "kasanatta": "💜 重なった知", "suuchi": "🩶 数値データ"}[x],
        )

        submitted = st.form_submit_button("記録する")
        if submitted:
            conn = get_connection()
            conn.execute(
                """INSERT INTO farm_diary
                   (date, weather, crop, work_done, observation, question, hypothesis, source_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (str(entry_date), weather, crop, work_done, observation, question, hypothesis, source_type),
            )
            conn.commit()
            conn.close()
            save_farm_diary(entry_date, weather, crop, work_done, observation, question, hypothesis, source_type)
            st.success("記録しました。（Notionにも同期）")
            st.rerun()

# ── 一覧表示 ──────────────────────────────────────────────
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
