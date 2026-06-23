import streamlit as st
import pandas as pd
from db.database import get_connection
from components.knowledge_card import knowledge_card
from utils.notion_sync import save_recipe
from utils.ai_advisor import get_ai_response_recipe, MAX_TURNS

st.set_page_config(page_title="料理", page_icon="🍳", layout="wide")
st.title("🍳 料理")
st.caption("畑の延長。収穫物から旬・保存性・原価率を考えてレシピを記録する。")

SEASONS = ["春", "夏", "秋", "冬", "通年"]

if "recipe_entry" not in st.session_state:
    st.session_state.recipe_entry = None
if "recipe_chat" not in st.session_state:
    st.session_state.recipe_chat = []
if "recipe_responses" not in st.session_state:
    st.session_state.recipe_responses = []

with st.expander("📝 レシピを記録する", expanded=True):
    with st.form("recipe_form"):
        col1, col2 = st.columns(2)
        with col1:
            recipe_name = st.text_input("料理名", placeholder="例：ナスの味噌炒め")
            vegetable   = st.text_input("主な野菜", placeholder="例：ナス、ピーマン")
            season      = st.selectbox("旬・季節", SEASONS)
        with col2:
            ingredients = st.text_area("材料・分量", placeholder="例：ナス2本、味噌大さじ2…")
            notes       = st.text_area("メモ（保存法・原価・人気度）",
                                       placeholder="例：田心カフェで好評。原価率25%")

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

            st.session_state.recipe_entry = {
                "recipe_name": recipe_name, "vegetable": vegetable,
                "ingredients": ingredients, "season": season, "notes": notes,
            }
            st.session_state.recipe_chat      = []
            st.session_state.recipe_responses = []

            with st.spinner("AI勘ちゃんが考えています…"):
                reply = get_ai_response_recipe(st.session_state.recipe_entry, [])
            st.session_state.recipe_responses.append({"role": "assistant", "content": reply})
            st.session_state.recipe_chat.append({"role": "assistant", "content": reply})
            st.success("記録しました。（Notionにも同期）")
            st.rerun()

# ── AI対話 ────────────────────────────────────────────────
if st.session_state.recipe_entry:
    st.markdown("---")
    st.subheader("🤝 AI勘ちゃんからのコメント")
    st.caption(f"料理：{st.session_state.recipe_entry.get('recipe_name','—')}　｜　最大{MAX_TURNS}回の対話")

    for msg in st.session_state.recipe_responses:
        avatar = "🌱" if msg["role"] == "assistant" else "👨‍🌾"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    user_turns = sum(1 for m in st.session_state.recipe_chat if m["role"] == "user")
    if user_turns < MAX_TURNS - 1:
        user_input = st.chat_input(f"勘ちゃんへの返事・追加の問い（あと{MAX_TURNS - 1 - user_turns}回）")
        if user_input:
            st.session_state.recipe_responses.append({"role": "user", "content": user_input})
            st.session_state.recipe_chat.append({"role": "user", "content": user_input})
            with st.spinner("勘ちゃんが考えています…"):
                reply = get_ai_response_recipe(
                    st.session_state.recipe_entry, st.session_state.recipe_chat)
            st.session_state.recipe_responses.append({"role": "assistant", "content": reply})
            st.session_state.recipe_chat.append({"role": "assistant", "content": reply})
            st.rerun()
    else:
        st.info("今日の対話はここまで。食べる。循環する。🌱")

    if st.button("対話をリセット"):
        st.session_state.recipe_entry     = None
        st.session_state.recipe_chat      = []
        st.session_state.recipe_responses = []
        st.rerun()

# ── 一覧 ─────────────────────────────────────────────────
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
        mask = (df["recipe_name"].str.contains(search, case=False, na=False) |
                df["vegetable"].str.contains(search, case=False, na=False))
        df = df[mask]
    if season_filter != "すべて":
        df = df[df["season"] == season_filter]

    for _, row in df.iterrows():
        title = f"{row['recipe_name']}（{row['season']}）"
        parts = []
        for label, key in [("野菜", "vegetable"), ("材料", "ingredients"), ("メモ", "notes")]:
            if row.get(key):
                parts.append(f"{label}：{row[key]}")
        knowledge_card(title, "\n".join(parts), row.get("source_type", "souhatsuchi"))
