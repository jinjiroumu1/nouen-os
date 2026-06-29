import streamlit as st
from utils.ai_advisor import get_ai_response_accounting, extract_delivery_note
from utils.sheets_loader import load_sheets, append_cost_row, upload_delivery_photo, search_delivery_photos
from utils.notion_sync import save_accounting_log, save_accounting_decision, load_accounting_decisions, save_purchase_record
from pathlib import Path as _P

st.set_page_config(page_title="会計・原価管理", page_icon="💰", layout="wide")

_img = _P("docs/characters/price.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)

st.title("💰 会計・原価管理")
st.caption("販売・原価・支払いをAI勘ちゃんと一緒に確認する")

st.markdown("""
<style>
/* タブ全体 */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
/* 非選択タブ */
.stTabs [data-baseweb="tab"] {
    background-color: #f0f0f0;
    border-radius: 8px 8px 0 0;
    padding: 8px 24px;
    font-weight: 600;
    color: #555;
}
/* 選択中タブ */
.stTabs [aria-selected="true"] {
    background-color: #2e7d32;
    color: #ffffff !important;
    border-radius: 8px 8px 0 0;
}
</style>
""", unsafe_allow_html=True)

tab_ask, tab_reg = st.tabs(["💬 質問する", "📝 登録する"])

# ══════════════════════════════════════════════════════
# タブ① 質問する
# ══════════════════════════════════════════════════════
with tab_ask:

    # ── AI勘ちゃんに質問 ──────────────────────────────
    st.subheader("💬 AI勘ちゃんに質問する")
    st.caption("原価・売上・支払いについて何でも聞いてください。")

    if "accounting_chat" not in st.session_state:
        st.session_state.accounting_chat = []

    col_input, col_send = st.columns([5, 1])
    with col_input:
        user_input = st.text_input(
            "質問を入力",
            placeholder="例：なすのあげびたしの原価率は？　パンダ広場の売上合計は？",
            label_visibility="collapsed",
            key="accounting_text_input",
        )
    with col_send:
        send = st.button("送信", use_container_width=True)

    if send and user_input:
        with st.spinner("勘ちゃんが数字を確認しています…"):
            reply = get_ai_response_accounting(user_input, st.session_state.accounting_chat)
        st.session_state.accounting_chat.append({"role": "user", "content": user_input})
        st.session_state.accounting_chat.append({"role": "assistant", "content": reply})
        save_accounting_log(user_input, reply)

    # 直前の質問と回答を入力欄の下に表示
    if st.session_state.accounting_chat:
        last_q = st.session_state.accounting_chat[-2]["content"]
        last_a = st.session_state.accounting_chat[-1]["content"]
        st.info(f"**👨‍💼 質問：** {last_q}")
        st.success(f"**🌱 勘ちゃん：** {last_a}")

    # 直前を除く過去の質問を折りたたみで表示
    past = st.session_state.accounting_chat[:-2]
    if past:
        st.markdown("---")
        with st.expander("📋 過去の質問", expanded=False):
            for msg in past:
                if msg["role"] == "user":
                    st.info(f"**👨‍💼 質問：** {msg['content']}")
                else:
                    st.success(f"**🌱 勘ちゃん：** {msg['content']}")

    st.markdown("---")

    # ── 納品書検索 ────────────────────────────────────
    st.subheader("🔍 納品書を検索")
    st.caption("仕入先名・商品名・日付などのキーワードでGoogle Drive内の納品書画像を検索します。")

    search_kw = st.text_input("キーワードを入力", placeholder="例：二見酒店　しょうが　20260621", key="photo_search")

    if search_kw:
        with st.spinner("検索中…"):
            photo_results = search_delivery_photos(search_kw)

        if not photo_results:
            st.info("該当する納品書が見つかりませんでした。")
        else:
            st.success(f"{len(photo_results)} 件見つかりました")
            cols = st.columns(3)
            for idx, item in enumerate(photo_results):
                with cols[idx % 3]:
                    if item["thumb"]:
                        st.image(item["thumb"], use_container_width=True)
                    else:
                        st.markdown("🖼️ （プレビューなし）")
                    st.markdown(f"**{item['name']}**")
                    st.markdown(f"[🔗 Driveで開く]({item['link']})")

    st.markdown("---")

    # ── スプレッドシートデータ確認 ────────────────────
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


# ══════════════════════════════════════════════════════
# タブ② 登録する
# ══════════════════════════════════════════════════════
with tab_reg:
    st.markdown("""
<style>
div[data-testid="stRadio"] > div { gap: 6px; }
div[data-testid="stRadio"] label {
    font-size: 0.82rem !important;
    color: #666 !important;
    padding: 3px 10px;
    border: 1px solid #ddd;
    border-radius: 12px;
    background: #f7f7f7;
}
div[data-testid="stRadio"] label[data-checked="true"] {
    background: #e8f5e9 !important;
    color: #2e7d32 !important;
    border-color: #a5d6a7 !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)
    reg_sub = st.radio("", ["🛒 仕入れを登録する", "💴 決まった売値の登録"],
                       horizontal=True, label_visibility="collapsed", key="reg_subtab")

if reg_sub == "🛒 仕入れを登録する":
    st.subheader("🛒 仕入れを登録する")
    st.caption("仕入れた商品を記録します。送料・消費税を自動計算してNotionに保存します。")

    with st.expander("📷 納品書写真から原価計算", expanded=False):
        st.warning("※手書きの納品書は認識精度が低いため、使用しないでください。印字された納品書のみ対応しています。")
        st.caption("納品書をアップロードすると複数商品をまとめて読み取ります。")
        dn_uploaded = st.file_uploader("納品書画像（JPG / PNG）", type=["jpg", "jpeg", "png"], key="dn_upload_top")
        if dn_uploaded:
            st.image(dn_uploaded, width=300)
            if st.button("🔍 AIで情報を抽出する", key="dn_extract_top"):
                with st.spinner("勘ちゃんが読み取っています…"):
                    mime = "image/jpeg" if dn_uploaded.type in ("image/jpeg", "image/jpg") else "image/png"
                    img_bytes = dn_uploaded.read()
                    result = extract_delivery_note(img_bytes, mime)
                if "error" in result:
                    st.error(f"抽出エラー: {result['error']}")
                else:
                    items_dn = result.get("items") or []
                    if not items_dn:
                        items_dn = [{"product_name": "", "purchase_price": 0, "total_quantity": 0, "unit_quantity": 0, "unit": "g"}]
                    st.session_state["dn_date"]      = str(result.get("date") or "")
                    st.session_state["dn_farmer"]    = str(result.get("farmer_name") or "")
                    st.session_state["dn_shipping"]  = float(result.get("shipping_fee") or 0)
                    st.session_state["dn_items"]     = items_dn
                    st.session_state["dn_image"]     = img_bytes
                    st.session_state["dn_orig_name"] = dn_uploaded.name
                    st.success(f"抽出完了！{len(items_dn)} 商品を読み取りました。下の「📷 納品書写真から原価計算」セクションで確認・保存してください。")

    if "purchase_items" not in st.session_state:
        st.session_state.purchase_items = [{"name": "", "unit_price": 0.0, "quantity": 1}]

    col_d, col_s, col_t = st.columns(3)
    with col_d:
        p_date = st.date_input("仕入日", key="p_date")
    with col_s:
        p_supplier = st.text_input("取引先", placeholder="例：二見酒店", key="p_supplier")
    with col_t:
        p_tax = st.radio("消費税区分", ["税込", "税別"], horizontal=True, key="p_tax")

    p_shipping = st.number_input("送料（円・任意）", min_value=0.0, step=10.0, key="p_shipping")

    st.markdown("**商品リスト**")
    items = st.session_state.purchase_items
    for i, item in enumerate(items):
        c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
        with c1:
            items[i]["name"] = st.text_input("商品名", value=item["name"], key=f"p_name_{i}", placeholder="例：A生樽20L")
        with c2:
            items[i]["unit_price"] = st.number_input("商品単価（円）", value=float(item["unit_price"]), step=1.0, key=f"p_price_{i}")
        with c3:
            items[i]["quantity"] = st.number_input("仕入個数", value=int(item["quantity"]), min_value=1, step=1, key=f"p_qty_{i}")
        with c4:
            if st.button("🗑️", key=f"p_del_{i}") and len(items) > 1:
                st.session_state.purchase_items.pop(i)
                st.rerun()

    if st.button("➕ 商品を追加", key="p_add"):
        st.session_state.purchase_items.append({"name": "", "unit_price": 0.0, "quantity": 1})
        st.rerun()

    p_note = st.text_input("備考（任意）", key="p_note")

    # 計算プレビュー
    total_qty = sum(it["quantity"] for it in items)
    # 計算ロジックを共通化
    def _calc(it):
        base = it["unit_price"]
        if p_tax == "税別":
            taxed_price = base * 1.08
            ship_per_unit = (p_shipping * 1.10 / total_qty) if total_qty > 0 else 0
        else:
            taxed_price = base
            ship_per_unit = (p_shipping / total_qty) if total_qty > 0 else 0
        total_unit = taxed_price + ship_per_unit
        return taxed_price, ship_per_unit, total_unit

    st.markdown("---")
    tax_note = "（単価×1.08、送料×1.10で按分）" if p_tax == "税別" else "（税込のまま按分）"
    st.markdown(f"**📊 計算プレビュー** {tax_note}")
    preview_rows = []
    for it in items:
        taxed_price, ship_per_unit, total_unit = _calc(it)
        preview_rows.append({
            "商品名":           it["name"] or "（未入力）",
            "単価（税込）":     f"¥{taxed_price:.1f}",
            "個数":             it["quantity"],
            "1個あたり按分送料": f"¥{ship_per_unit:.1f}",
            "商品単価合計":     f"¥{total_unit:.1f}",
        })
    import pandas as _pd
    st.dataframe(_pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

    if st.button("💾 仕入れを保存する", key="p_save"):
        errors = []
        for it in items:
            taxed_price, ship_per_unit, total_unit = _calc(it)
            ok = save_purchase_record(
                purchase_date    = str(p_date),
                supplier         = p_supplier,
                product_name     = it["name"],
                unit_price       = it["unit_price"],
                quantity         = it["quantity"],
                shipping         = round(ship_per_unit, 1),
                tax_type         = p_tax,
                total_unit_price = round(total_unit, 1),
                note             = p_note,
            )
            if not ok:
                errors.append(it["name"] or "（未入力）")
        if errors:
            st.error(f"保存失敗: {', '.join(errors)}")
        else:
            st.success(f"✅ {len(items)} 件の仕入れを保存しました！")
            st.session_state.purchase_items = [{"name": "", "unit_price": 0.0, "quantity": 1}]
            st.rerun()

if reg_sub == "💴 決まった売値の登録":
    # ── 決まった売値の登録 ──────────────────────────
    st.subheader("💴 決まった売値の登録")
    st.caption("売値・ルールなどチームの決め事を記録してAI勘ちゃんが参照します。")

    with st.form("decision_form", clear_on_submit=True):
        dec_category = st.radio("カテゴリ", ["🏷️ 売値", "📋 ルール"], horizontal=True)
        dec_item     = st.text_input("品物名",        placeholder="例：ネーブルオレンジ")
        dec_qty      = st.text_input("量",             placeholder="例：1個、1kg、1箱")
        dec_price    = st.text_input("金額（円）",     placeholder="例：500円")
        dec_note     = st.text_input("備考（任意）",   placeholder="例：パンダ広場・いきいき共通")
        submitted    = st.form_submit_button("💾 保存する")
        if submitted:
            if dec_item and dec_price:
                ok = save_accounting_decision(dec_item, dec_category, dec_qty, dec_price, dec_note)
                if ok:
                    st.success("✅ 決め事を保存しました！")
                else:
                    st.error("保存に失敗しました。Notion設定を確認してください。")
            else:
                st.warning("品物名と金額は必須です。")

    decisions = load_accounting_decisions()
    if decisions:
        st.markdown("**📋 登録済みの決め事**")
        for d in decisions:
            cat   = d.get("category", "")
            qty   = f"　{d['quantity']}" if d.get("quantity") else ""
            note  = f"　（{d['note']}）" if d.get("note") else ""
            st.markdown(f"- {cat} **{d['item_name']}**{qty}　→　{d['price']}{note}")
    else:
        st.caption("まだ決め事が登録されていません。")

