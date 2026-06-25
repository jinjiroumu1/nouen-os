import streamlit as st
import pandas as pd
from db.database import get_connection
from components.knowledge_card import knowledge_card
from utils.notion_sync import save_cultivation_plan
from utils.ai_advisor import get_ai_response_cultivation, MAX_TURNS

st.set_page_config(page_title="栽培計画", page_icon="📅", layout="wide")
from pathlib import Path as _P
_img = _P("docs/characters/pop.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)
st.title("📅 栽培計画")
st.caption("季節・育てやすさ・コンパニオンプランツを考慮して計画する。")

MONTHS = [f"{i}月" for i in range(1, 13)]

if "cultivation_entry" not in st.session_state:
    st.session_state.cultivation_entry = None
if "cultivation_chat" not in st.session_state:
    st.session_state.cultivation_chat = []
if "cultivation_responses" not in st.session_state:
    st.session_state.cultivation_responses = []

with st.expander("📝 栽培計画を追加する", expanded=True):
    with st.form("plan_form"):
        col1, col2 = st.columns(2)
        with col1:
            month         = st.selectbox("月", MONTHS)
            crop          = st.text_input("作物名", placeholder="例：ナス")
            sowing_date   = st.text_input("播種時期", placeholder="例：3月中旬")
            planting_date = st.text_input("定植時期", placeholder="例：5月上旬")
        with col2:
            harvest_period    = st.text_input("収穫時期", placeholder="例：7月〜9月")
            companion_plants  = st.text_input("コンパニオンプランツ", placeholder="例：バジル、マリーゴールド")
            required_materials = st.text_area("必要資材", placeholder="例：支柱、マルチシート")

        source_type = st.selectbox(
            "知識の種別",
            ["souhatsuchi", "kenjinchi", "kasanatta"],
            format_func=lambda x: {"souhatsuchi": "🌸 創発知", "kenjinchi": "💙 賢人知",
                                   "kasanatta": "💜 重なった知"}[x],
        )

        submitted = st.form_submit_button("追加する")
        if submitted and crop:
            conn = get_connection()
            conn.execute(
                """INSERT INTO cultivation_plans
                   (month, crop, sowing_date, planting_date, harvest_period,
                    companion_plants, required_materials, source_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (month, crop, sowing_date, planting_date, harvest_period,
                 companion_plants, required_materials, source_type),
            )
            conn.commit()
            conn.close()
            save_cultivation_plan(month, crop, sowing_date, planting_date, harvest_period,
                                  companion_plants, required_materials, source_type)

            st.session_state.cultivation_entry = {
                "month": month, "crop": crop, "sowing_date": sowing_date,
                "planting_date": planting_date, "harvest_period": harvest_period,
                "companion_plants": companion_plants, "required_materials": required_materials,
            }
            st.session_state.cultivation_chat      = []
            st.session_state.cultivation_responses = []

            with st.spinner("AI勘ちゃんが考えています…"):
                reply = get_ai_response_cultivation(st.session_state.cultivation_entry, [])
            st.session_state.cultivation_responses.append({"role": "assistant", "content": reply})
            st.session_state.cultivation_chat.append({"role": "assistant", "content": reply})
            st.success("追加しました。（Notionにも同期）")
            st.rerun()

# ── AI対話 ────────────────────────────────────────────────
if st.session_state.cultivation_entry:
    st.markdown("---")
    st.subheader("🤝 AI勘ちゃんからのコメント")
    st.caption(f"作物：{st.session_state.cultivation_entry.get('crop','—')}　｜　最大{MAX_TURNS}回の対話")

    for msg in st.session_state.cultivation_responses:
        avatar = "🌱" if msg["role"] == "assistant" else "👨‍🌾"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    user_turns = sum(1 for m in st.session_state.cultivation_chat if m["role"] == "user")
    if user_turns < MAX_TURNS - 1:
        user_input = st.chat_input(f"勘ちゃんへの返事・追加の問い（あと{MAX_TURNS - 1 - user_turns}回）")
        if user_input:
            st.session_state.cultivation_responses.append({"role": "user", "content": user_input})
            st.session_state.cultivation_chat.append({"role": "user", "content": user_input})
            with st.spinner("勘ちゃんが考えています…"):
                reply = get_ai_response_cultivation(
                    st.session_state.cultivation_entry, st.session_state.cultivation_chat)
            st.session_state.cultivation_responses.append({"role": "assistant", "content": reply})
            st.session_state.cultivation_chat.append({"role": "assistant", "content": reply})
            st.rerun()
    else:
        st.info("今日の対話はここまで。育てる。循環する。🌱")

    if st.button("対話をリセット"):
        st.session_state.cultivation_entry    = None
        st.session_state.cultivation_chat     = []
        st.session_state.cultivation_responses = []
        st.rerun()

# ── 一覧 ─────────────────────────────────────────────────
st.markdown("---")
st.subheader("栽培計画一覧")

conn = get_connection()
rows = conn.execute("SELECT * FROM cultivation_plans ORDER BY id DESC").fetchall()
conn.close()

if not rows:
    st.info("まだ栽培計画がありません。")
else:
    df = pd.DataFrame([dict(r) for r in rows])
    month_filter = st.selectbox("月で絞り込み", ["すべて"] + MONTHS)
    if month_filter != "すべて":
        df = df[df["month"] == month_filter]

    for _, row in df.iterrows():
        title = f"{row['month']} ／ {row['crop']}"
        parts = []
        for label, key in [("播種", "sowing_date"), ("定植", "planting_date"),
                            ("収穫", "harvest_period"), ("コンパニオン", "companion_plants"),
                            ("資材", "required_materials")]:
            if row.get(key):
                parts.append(f"{label}：{row[key]}")
        knowledge_card(title, "\n".join(parts), row.get("source_type", "souhatsuchi"))
