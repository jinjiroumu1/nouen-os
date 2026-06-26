import streamlit as st
from utils.ai_advisor import get_ai_response_accounting, extract_delivery_note
from utils.sheets_loader import load_sheets, append_cost_row, upload_delivery_photo
from utils.notion_sync import save_accounting_log

st.set_page_config(page_title="会計・原価管理", page_icon="💰", layout="wide")
from pathlib import Path as _P
_img = _P("docs/characters/price.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)
st.title("💰 会計・原価管理")
st.caption("販売・原価・支払いをAI勘ちゃんと一緒に確認する")

# ── チャット ──────────────────────────────────────────────
st.subheader("💬 AI勘ちゃんに質問する")
st.caption("原価・売上・支払いについて何でも聞いてください。")

if "accounting_chat" not in st.session_state:
    st.session_state.accounting_chat = []

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
    save_accounting_log(user_input, reply)

if st.session_state.accounting_chat and st.button("チャットをリセット"):
    st.session_state.accounting_chat = []
    st.rerun()

st.markdown("---")

# ── 納品書写真読み取り ─────────────────────────────────────
st.subheader("📷 納品書写真から原価計算")
st.caption("納品書の写真をアップロードすると、AI勘ちゃんが自動で情報を抽出します。")

uploaded = st.file_uploader("納品書画像をアップロード（JPG / PNG）", type=["jpg", "jpeg", "png"])

if uploaded:
    st.image(uploaded, width=300)

    if st.button("🔍 AIで情報を抽出する"):
        with st.spinner("勘ちゃんが納品書を読み取っています…"):
            mime = "image/jpeg" if uploaded.type in ("image/jpeg", "image/jpg") else "image/png"
            img_bytes = uploaded.read()
            result = extract_delivery_note(img_bytes, mime)

        if "error" in result:
            st.error(f"抽出エラー: {result['error']}")
        else:
            st.session_state["delivery_note"] = result
            st.session_state["delivery_image"] = img_bytes
            st.session_state["delivery_filename"] = uploaded.name
            st.success("抽出完了！内容を確認・編集してください。")

if "delivery_note" in st.session_state:
    dn = st.session_state["delivery_note"]
    st.markdown("#### 抽出結果（編集可能）")

    col1, col2 = st.columns(2)
    with col1:
        date         = st.text_input("日付",         value=str(dn.get("date") or ""))
        product_name = st.text_input("商品名",       value=str(dn.get("product_name") or ""))
        farmer_name  = st.text_input("農家さん名",   value=str(dn.get("farmer_name") or ""))
    with col2:
        purchase_price = st.number_input("仕入価格（円）",     value=float(dn.get("purchase_price") or 0), step=1.0)
        shipping_fee   = st.number_input("送料（円）",         value=float(dn.get("shipping_fee") or 0),   step=1.0)
        total_weight   = st.number_input("全体の重さ（g）",    value=float(dn.get("total_weight") or 0),   step=1.0)
        unit_weight    = st.number_input("1商品の重さ（g）",   value=float(dn.get("unit_weight") or 0),    step=1.0)

    # 原価・粗利の自動計算
    if total_weight > 0:
        cost = (purchase_price + shipping_fee) * unit_weight / total_weight
    else:
        cost = 0.0

    selling_price = st.number_input("販売価格（円）", value=0.0, step=1.0)
    gross_profit  = selling_price - cost
    note          = st.text_input("備考（K列）", value="")

    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("原価", f"¥{cost:.1f}")
    col_b.metric("販売価格", f"¥{selling_price:.1f}")
    col_c.metric("粗利", f"¥{gross_profit:.1f}")

    if st.button("📊 スプレッドシートに保存"):
        # 写真をDriveにアップロード
        photo_link = ""
        img_bytes = st.session_state.get("delivery_image")
        if img_bytes:
            safe_date = date.replace("/", "-").replace(" ", "")
            safe_name = product_name.replace("/", "・")
            fname = f"納品書_{safe_date}_{safe_name}.jpg"
            with st.spinner("写真をGoogle Driveに保存しています…"):
                photo_link = upload_delivery_photo(img_bytes, fname) or ""

        row = [
            date, product_name, farmer_name,
            purchase_price, shipping_fee,
            total_weight, unit_weight,
            round(cost, 1), selling_price, round(gross_profit, 1),
            note, photo_link,
        ]
        ok = append_cost_row(row)
        if ok:
            st.success("スプレッドシートに保存しました！" + ("　📸 写真も保存しました。" if photo_link else ""))
            for key in ("delivery_note", "delivery_image", "delivery_filename"):
                st.session_state.pop(key, None)
        else:
            st.error("保存に失敗しました。Secretsとスプレッドシートの共有設定を確認してください。")

st.markdown("---")

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
