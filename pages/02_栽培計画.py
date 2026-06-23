import streamlit as st
import pandas as pd
from db.database import get_connection
from components.knowledge_card import knowledge_card
from utils.notion_sync import save_cultivation_plan

st.set_page_config(page_title="栽培計画", page_icon="📅", layout="wide")
st.title("📅 栽培計画")
st.caption("季節・育てやすさ・コンパニオンプランツを考慮して計画する。")

MONTHS = [f"{i}月" for i in range(1, 13)]

with st.expander("📝 栽培計画を追加する", expanded=True):
    with st.form("plan_form"):
        col1, col2 = st.columns(2)
        with col1:
            month = st.selectbox("月", MONTHS)
            crop = st.text_input("作物名", placeholder="例：ナス")
            sowing_date = st.text_input("播種時期", placeholder="例：3月中旬")
            planting_date = st.text_input("定植時期", placeholder="例：5月上旬")
        with col2:
            harvest_period = st.text_input("収穫時期", placeholder="例：7月〜9月")
            companion_plants = st.text_input("コンパニオンプランツ", placeholder="例：バジル、マリーゴールド")
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
            st.success("追加しました。（Notionにも同期）")
            st.rerun()

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
        if row.get("sowing_date"):
            parts.append(f"播種：{row['sowing_date']}")
        if row.get("planting_date"):
            parts.append(f"定植：{row['planting_date']}")
        if row.get("harvest_period"):
            parts.append(f"収穫：{row['harvest_period']}")
        if row.get("companion_plants"):
            parts.append(f"コンパニオン：{row['companion_plants']}")
        if row.get("required_materials"):
            parts.append(f"資材：{row['required_materials']}")
        knowledge_card(title, "\n".join(parts), row.get("source_type", "souhatsuchi"))
