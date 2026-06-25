import streamlit as st
from utils.ai_advisor import get_ai_response_accounting
from utils.sheets_loader import load_sheets
from utils.invoice_loader import load_invoices

st.set_page_config(page_title="会計・原価管理", page_icon="💰", layout="wide")
from pathlib import Path as _P
_img = _P("docs/characters/price.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)
st.title("💰 会計・原価管理")
st.caption("販売・原価・支払いをAI勘ちゃんと一緒に確認する")

# ── スプレッドシートデータ確認 ────────────────────────────
with st.expander("📊 読み込み中のスプレッドシートデータ"):
    sheets_text = load_sheets()
    if sheets_text:
        st.text(sheets_text[:2000])
    else:
        st.info(
            "スプレッドシートが未設定です。\n"
            "Streamlit Cloud の Secrets に以下を追加してください：\n"
            "SHEET_COST / SHEET_PANDA / SHEET_IKIKI / SHEET_PAYMENT"
        )

with st.expander("📄 読み込み中の請求書PDF"):
    invoices = load_invoices()
    if invoices:
        for inv in invoices:
            st.markdown(f"- {inv['name']}")
    else:
        st.info(
            "請求書PDFが見つかりません。\n"
            "Streamlit Cloud の Secrets に `INVOICE_FOLDER_ID` を追加し、\n"
            "Google Drive フォルダをサービスアカウントと共有してください。"
        )

st.markdown("---")

# ── チャット ──────────────────────────────────────────────
st.subheader("💬 AI勘ちゃんに質問する")
st.caption("原価・売上・支払いについて何でも聞いてください。スプレッドシートのデータをもとに回答します。")

if "accounting_chat" not in st.session_state:
    st.session_state.accounting_chat = []

# 過去の対話を表示
for msg in st.session_state.accounting_chat:
    avatar = "👨‍🌾" if msg["role"] == "user" else "🌱"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

user_input = st.chat_input(
    "例：なすのあげびたしの原価率は？　パンダ広場の売上合計は？　未払いの支払いは？"
)
if user_input:
    st.session_state.accounting_chat.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👨‍🌾"):
        st.markdown(user_input)

    with st.spinner("勘ちゃんが数字を確認しています…"):
        reply = get_ai_response_accounting(
            user_input, st.session_state.accounting_chat[:-1]
        )

    st.session_state.accounting_chat.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant", avatar="🌱"):
        st.markdown(reply)

if st.session_state.accounting_chat and st.button("チャットをリセット"):
    st.session_state.accounting_chat = []
    st.rerun()
