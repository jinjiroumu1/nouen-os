import streamlit as st
from utils.ai_advisor import get_ai_response_accounting, extract_delivery_note
from utils.sheets_loader import load_sheets, append_cost_row, upload_delivery_photo
from utils.notion_sync import save_accounting_log
from pathlib import Path as _P

st.set_page_config(page_title="会計・原価管理", page_icon="💰", layout="wide")

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

user_input = st.chat_input("例：なすのあげびたしの原価率は？　パンダ広場の売上合計は？")
if user_input:
    st.session_state.accounting_chat.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👨‍🌾"):
        st.markdown(user_input)
    with st.spinner("勘ちゃんが数字を確認しています…"):
        reply = get_ai_response_accounting(user_input, st.session_state.accounting_chat[:-1])
    st.session_state.accounting_chat.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant", avatar="🌱"):
        st.markdown(reply)
    save_accounting_log(user_input, reply)

if st.session_state.accounting_chat and st.button("チャットをリセット"):
    st.session_state.accounting_chat = []
    st.rerun()

st.markdown("---")

# ── 納品書写真読み取り（複数商品対応）────────────────────
st.subheader("📷 納品書写真から原価計算")
st.caption("納品書をアップロードすると複数商品をまとめて読み取ります。")

uploaded = st.file_uploader("納品書画像（JPG / PNG）", type=["jpg", "jpeg", "png"])

if uploaded:
    st.image(uploaded, width=300)
    if st.button("🔍 AIで情報を抽出する"):
        with st.spinner("勘ちゃんが読み取っています…"):
            mime = "image/jpeg" if uploaded.type in ("image/jpeg", "image/jpg") else "image/png"
            img_bytes = uploaded.read()
            result = extract_delivery_note(img_bytes, mime)
        if "error" in result:
            st.error(f"抽出エラー: {result['error']}")
        else:
            # items が空またはない場合は1商品として補完
            items = result.get("items") or []
            if not items:
                items = [{"product_name": "", "purchase_price": 0, "total_weight": 0, "unit_weight": 0}]
            st.session_state["dn_date"]         = str(result.get("date") or "")
            st.session_state["dn_farmer"]       = str(result.get("farmer_name") or "")
            st.session_state["dn_shipping"]     = float(result.get("shipping_fee") or 0)
            st.session_state["dn_items"]        = items
            st.session_state["dn_image"]        = img_bytes
            st.session_state["dn_orig_name"]    = uploaded.name
            st.success(f"抽出完了！{len(items)} 商品を読み取りました。")

# ── 編集フォーム ──────────────────────────────────────────
if "dn_items" in st.session_state:
    st.markdown("#### 抽出結果（編集可能）")

    col1, col2, col3 = st.columns(3)
    with col1:
        date = st.text_input("日付", value=st.session_state["dn_date"], key="edit_date")
    with col2:
        farmer_name = st.text_input("農家さん名", value=st.session_state["dn_farmer"], key="edit_farmer")
    with col3:
        shipping_fee = st.number_input("送料合計（円）", value=st.session_state["dn_shipping"], step=1.0, key="edit_shipping")

    note = st.text_input("備考（K列・全行共通）", value="", key="edit_note")

    st.markdown("---")
    st.markdown("**商品ごとの内訳**（送料は商品数で按分）")

    items = st.session_state["dn_items"]
    n = len(items)
    shipping_per_item = shipping_fee / n if n > 0 else 0

    edited_items = []
    for i, item in enumerate(items):
        st.markdown(f"**商品 {i+1}**")
        c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 2, 1])
        with c1:
            pname = st.text_input("商品名", value=str(item.get("product_name") or ""), key=f"pname_{i}")
        with c2:
            pprice = st.number_input("仕入価格（円）", value=float(item.get("purchase_price") or 0), step=1.0, key=f"pprice_{i}")
        with c3:
            tw = st.number_input("全体の重さ（g）", value=float(item.get("total_weight") or 0), step=1.0, key=f"tw_{i}")
        with c4:
            uw = st.number_input("1商品の重さ（g）", value=float(item.get("unit_weight") or 0), step=1.0, key=f"uw_{i}")
        with c5:
            sp = st.number_input("販売価格（円）", value=0.0, step=1.0, key=f"sp_{i}")
        with c6:
            if st.button("🗑️", key=f"del_{i}") and n > 1:
                st.session_state["dn_items"].pop(i)
                st.rerun()

        cost = (pprice + shipping_per_item) * uw / tw if tw > 0 else 0.0
        gross = sp - cost
        st.caption(f"按分送料: ¥{shipping_per_item:.1f}　原価: ¥{cost:.1f}　粗利: ¥{gross:.1f}")

        edited_items.append({
            "product_name": pname,
            "purchase_price": pprice,
            "total_weight": tw,
            "unit_weight": uw,
            "selling_price": sp,
            "cost": cost,
            "gross": gross,
        })

    if st.button("➕ 行を追加"):
        st.session_state["dn_items"].append({"product_name": "", "purchase_price": 0, "total_weight": 0, "unit_weight": 0})
        st.rerun()

    st.markdown("---")

    if st.button("📊 まとめて保存"):
        # 写真をDriveにアップロード
        photo_link = ""
        img_bytes = st.session_state.get("dn_image")
        if img_bytes:
            safe_date = date.replace("/", "-").replace(" ", "")
            fname = f"納品書_{safe_date}_{farmer_name}.jpg"
            with st.spinner("写真をGoogle Driveに保存しています…"):
                photo_link = upload_delivery_photo(img_bytes, fname) or ""

        errors = []
        for item in edited_items:
            row = [
                date,
                item["product_name"],
                farmer_name,
                item["purchase_price"],
                round(shipping_per_item, 1),
                item["total_weight"],
                item["unit_weight"],
                round(item["cost"], 1),
                item["selling_price"],
                round(item["gross"], 1),
                note,
                photo_link,
            ]
            if not append_cost_row(row):
                errors.append(item["product_name"])

        if errors:
            st.error(f"以下の行の保存に失敗しました: {', '.join(errors)}")
        else:
            st.success(f"{len(edited_items)} 行を保存しました！" + ("　📸 写真も保存しました。" if photo_link else ""))
            for key in ("dn_date", "dn_farmer", "dn_shipping", "dn_items", "dn_image", "dn_orig_name"):
                st.session_state.pop(key, None)
            st.rerun()

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
