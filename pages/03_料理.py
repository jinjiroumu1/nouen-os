import streamlit as st
from utils.notion_sync import save_recipe_chat_log, load_recipe_chat_logs
from utils.ai_advisor import get_ai_response_recipe, MAX_TURNS

st.set_page_config(page_title="料理", page_icon="🍳", layout="wide")
from pathlib import Path as _P
_img = _P("docs/characters/midori.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)
st.title("🍳 料理")

QUERY_OPTIONS = ["料理を検索", "野菜の見分け方", "保存方法"]

if "recipe_entry" not in st.session_state:
    st.session_state.recipe_entry = None
if "recipe_chat" not in st.session_state:
    st.session_state.recipe_chat = []
if "recipe_responses" not in st.session_state:
    st.session_state.recipe_responses = []

# ── 野菜質問エリア ────────────────────────────────────────
vegetable_q = st.text_input("知りたい野菜", placeholder="例：にんじん")
st.write("知りたいことを選んでください（複数選択可）")
cb_cols = st.columns(len(QUERY_OPTIONS))
query_types = [opt for i, opt in enumerate(QUERY_OPTIONS) if cb_cols[i].checkbox(opt)]

btn_disabled = not (vegetable_q and query_types)
b1, b2 = st.columns([2, 3])
btn_normal = b1.button("質問する", type="primary", disabled=btn_disabled)
btn_tetsu  = b2.button("🧑‍🌾 青髪のテツさんに聞く", disabled=btn_disabled)

use_tetsu = btn_tetsu  # どちらのボタンを押したか

if btn_normal or btn_tetsu:
    st.session_state.recipe_entry = {
        "vegetable":   vegetable_q,
        "recipe_name": "",
        "ingredients": "",
        "season":      "",
        "notes":       "",
    }
    st.session_state.recipe_chat      = []
    st.session_state.recipe_responses = []
    spinner_msg = "青髪のテツさんのブログを調べています…" if use_tetsu else "AI勘ちゃんが調べています…"
    with st.spinner(spinner_msg):
        reply = get_ai_response_recipe(
            st.session_state.recipe_entry, [], query_types=query_types, use_tetsu=use_tetsu)
    st.session_state.recipe_responses.append({"role": "assistant", "content": reply})
    st.session_state.recipe_chat.append({"role": "assistant", "content": reply})
    save_recipe_chat_log(vegetable_q, query_types, reply)
    st.cache_data.clear()
    st.rerun()

# ── AI対話エリア ──────────────────────────────────────────
if st.session_state.recipe_entry:
    st.markdown("---")
    st.subheader("🤝 AI勘ちゃんの回答")

    for msg in st.session_state.recipe_responses:
        avatar = "🌱" if msg["role"] == "assistant" else "👨‍🌾"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    user_turns = sum(1 for m in st.session_state.recipe_chat if m["role"] == "user")
    if user_turns < MAX_TURNS - 1:
        with st.form("recipe_followup_form", clear_on_submit=True):
            user_input = st.text_input(f"追加の質問（あと{MAX_TURNS - 1 - user_turns}回）")
            submitted = st.form_submit_button("送信")
        if submitted and user_input:
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

# ── 過去の質問 ────────────────────────────────────────────
st.markdown("---")
with st.expander("📋 過去の質問"):
    logs = load_recipe_chat_logs(limit=20)
    if not logs:
        st.info("まだ質問履歴がありません。")
    else:
        for log in logs:
            with st.container(border=True):
                hc1, hc2 = st.columns([4, 2])
                hc1.markdown(f"**🥬 {log['vegetable']}**")
                hc2.caption(log.get("date", ""))
                if log.get("query_types"):
                    st.caption(f"質問種別：{log['query_types']}")
                if log.get("answer"):
                    st.markdown(log["answer"][:500] + ("…" if len(log["answer"]) > 500 else ""))
