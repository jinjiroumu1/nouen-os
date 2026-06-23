import streamlit as st
import pandas as pd
from db.database import get_connection
from components.knowledge_card import knowledge_card
from utils.notion_sync import save_recipe

st.set_page_config(page_title="料理", page_icon="🍳", layout="wide")
st.title("🍳 料理")
st.caption("畑の延長。収穫物から旬・保存性・原価率を考えてレシピを記録する。")

SEASONS = ["春", "夏", "秋", "冬", "通年"]

with st.expander("📝 レシピを記録する", expanded=True):
    with st.form("recipe_form"):
        col1, col2 = st.columns(2)
        with col1:
            recipe_name = st.text_input("料理名", placeholder="例：ナスの味噌炒め")
            vegetable = st.text_input("主な野菜", placeholder="例：ナス、ピーマン")
            season = st.selectbox("旬・季節", SEASONS)
        with col2:
            ingredients = st.text_area("材料・分量", placeholder="例：ナス2本、味噌大さじ2…")
            notes = st.text_area("メモ（保存法・原価・人気度）", placeholder="例：田心カフェで好評。原価率25%")

        source_type = st.selectbox(
            "知識の種別",
            ["souhatsuchi", "kenjinchi", "kasanatta"],
            format_func=lambda x: {"souhatsuchi": "🌸 創発知（自分たちのレシピ）",
                                   "kenjinchi": "💙 賢人知（書籍・引用）",
                                   "kasanatta": "💜 重なった知"}[x],
        )

        submitted = st.form_submit_button("記録する")
        if submitted and recipe_name:
            conn = get_connection()
            conn.execute(
                """INSERT INTO recipes
                   (recipe_name, vegetable, ingredients, season, notes, source_type)
                   VALUES (?,?,?,?,?,?)""",
                (recipe_name, vegetable, ingredients, season, notes, source_type),
            )
            conn.commit()
            conn.close()
            save_recipe(recipe_name, vegetable, ingredients, season, notes, source_type)
            st.success("記録しました。（Notionにも同期）")
            st.rerun()

st.markdown("---")
st.subheader("レシピ一覧")

conn = get_connection()
rows = conn.execute("SELECT * FROM recipes ORDER BY id DESC").fetchall()
conn.close()

if not rows:
    st.info("まだレシピがありません。")
else:
    df = pd.DataFrame([dict(r) for r in rows])

    col1, col2 = st.columns(2)
    with col1:
        search = st.text_input("🔍 料理名・野菜で絞り込み")
    with col2:
        season_filter = st.selectbox("季節で絞り込み", ["すべて"] + SEASONS)

    if search:
        mask = df["recipe_name"].str.contains(search, case=False, na=False) | \
               df["vegetable"].str.contains(search, case=False, na=False)
        df = df[mask]
    if season_filter != "すべて":
        df = df[df["season"] == season_filter]

    for _, row in df.iterrows():
        title = f"{row['recipe_name']}（{row['season']}）"
        parts = []
        if row.get("vegetable"):
            parts.append(f"野菜：{row['vegetable']}")
        if row.get("ingredients"):
            parts.append(f"材料：{row['ingredients']}")
        if row.get("notes"):
            parts.append(f"メモ：{row['notes']}")
        knowledge_card(title, "\n".join(parts), row.get("source_type", "souhatsuchi"))
