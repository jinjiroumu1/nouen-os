import streamlit as st
import streamlit.components.v1 as _components
from utils.ai_advisor import get_ai_response_accounting, extract_delivery_note
from utils.sheets_loader import load_sheets, append_cost_row, upload_delivery_photo, search_delivery_photos
from utils.notion_sync import (save_accounting_log, save_accounting_decision, load_accounting_decisions,
                               update_accounting_decision, save_purchase_record, load_purchase_records,
                               update_purchase_record)
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
        _do_scroll = st.session_state.pop("_scroll_top", False)
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

        # プリセットキー → ウィジェットキーへ転送（widget描画前）
        import datetime as _dt
        for _f, _t in [("p_supplier_pre","p_supplier"),("p_tax_pre","p_tax"),
                       ("p_shipping_pre","p_shipping"),("p_note_pre","p_note")]:
            if _f in st.session_state:
                st.session_state[_t] = st.session_state.pop(_f)
        if "p_date_pre" in st.session_state:
            _d = st.session_state.pop("p_date_pre")
            try:
                st.session_state["p_date"] = _dt.date.fromisoformat(str(_d)) if _d else _dt.date.today()
            except ValueError:
                st.session_state["p_date"] = _dt.date.today()

        if "purchase_items" not in st.session_state:
            st.session_state.purchase_items = [{"name": "", "unit_price": 0.0, "quantity": 1}]

        # 仕入日入力欄へのアンカー（修正ボタン後のスクロール先）
        st.markdown('<div id="purchase-form-top"></div>', unsafe_allow_html=True)
        if _do_scroll:
            _components.html("""<script>
              setTimeout(function(){
                var el = window.parent.document.getElementById('purchase-form-top');
                if(el) el.scrollIntoView({behavior:'smooth', block:'start'});
              }, 300);
            </script>""", height=0)

        col_d, col_s, col_t = st.columns(3)
        with col_d:
            p_date = st.date_input("仕入日", key="p_date")
        with col_s:
            p_supplier = st.text_input("取引先", placeholder="例：二見酒店", key="p_supplier")
        with col_t:
            p_tax = st.radio("消費税区分", ["税込", "税別"], horizontal=True, key="p_tax")

        p_shipping = st.number_input("送料（円・任意）", min_value=0.0, step=10.0, key="p_shipping")

        st.markdown("**商品リスト**")
        _rev = st.session_state.get("p_item_rev", 0)
        items = st.session_state.purchase_items
        for i, item in enumerate(items):
            c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
            with c1:
                items[i]["name"] = st.text_input("商品名", value=item["name"], placeholder="例：A生樽20L", key=f"p_name_{_rev}_{i}")
            with c2:
                items[i]["total_price"] = st.number_input("商品合計（円）", value=float(item.get("total_price", item.get("unit_price", 0.0))), step=1.0, key=f"p_price_{_rev}_{i}")
            with c3:
                items[i]["quantity"] = st.number_input("仕入個数", value=int(item["quantity"]), min_value=1, step=1, key=f"p_qty_{_rev}_{i}")
            with c4:
                if st.button("🗑️", key=f"p_del_{_rev}_{i}") and len(items) > 1:
                    st.session_state.purchase_items.pop(i)
                    st.rerun()

        if st.button("➕ 商品を追加", key=f"p_add_{_rev}"):
            st.session_state.purchase_items.append({"name": "", "total_price": 0.0, "quantity": 1})
            st.rerun()

        p_note = st.text_input("備考（任意）", key="p_note")

        # 計算プレビュー
        total_qty = sum(it["quantity"] for it in items)
        # 計算ロジック：商品合計÷個数で単価を逆算、そこに税・送料を加算
        def _calc(it):
            qty = it["quantity"] if it["quantity"] > 0 else 1
            unit_price = it.get("total_price", it.get("unit_price", 0.0)) / qty
            if p_tax == "税別":
                taxed_price = unit_price * 1.08
                ship_per_unit = (p_shipping * 1.10 / total_qty) if total_qty > 0 else 0
            else:
                taxed_price = unit_price
                ship_per_unit = (p_shipping / total_qty) if total_qty > 0 else 0
            total_unit = taxed_price + ship_per_unit
            return unit_price, taxed_price, ship_per_unit, total_unit

        st.markdown("---")
        tax_note = "（単価×1.08、送料×1.10で按分）" if p_tax == "税別" else "（税込のまま按分）"
        st.markdown(f"**📊 計算プレビュー** {tax_note}")
        preview_rows = []
        for it in items:
            unit_price, taxed_price, ship_per_unit, total_unit = _calc(it)
            preview_rows.append({
                "商品名":           it["name"] or "（未入力）",
                "商品合計":         f"¥{it.get('total_price', 0.0):.1f}",
                "個数":             it["quantity"],
                "逆算単価（税込）": f"¥{taxed_price:.1f}",
                "1個あたり按分送料": f"¥{ship_per_unit:.1f}",
                "商品単価合計":     f"¥{total_unit:.1f}",
            })
        import pandas as _pd
        st.dataframe(_pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

        edit_page_ids = st.session_state.get("p_edit_page_ids", [])
        is_edit = bool(edit_page_ids)
        btn_label = "💾 修正を保存する" if is_edit else "💾 仕入れを保存する"
        if is_edit:
            st.info(f"✏️ 修正モード：{len(edit_page_ids)} 件を上書き保存します")

        if st.button(btn_label, key="p_save"):
            errors = []
            n_items = len(items)
            for idx, it in enumerate(items):
                unit_price, taxed_price, ship_per_unit, total_unit = _calc(it)
                if is_edit and idx < len(edit_page_ids):
                    ok, err_msg = update_purchase_record(
                        page_id          = edit_page_ids[idx],
                        purchase_date    = str(p_date),
                        supplier         = p_supplier,
                        product_name     = it["name"],
                        unit_price       = round(unit_price, 1),
                        quantity         = it["quantity"],
                        shipping         = round(ship_per_unit, 1),
                        tax_type         = p_tax,
                        total_unit_price = round(total_unit, 1),
                        note             = p_note,
                    )
                else:
                    ok, err_msg = save_purchase_record(
                        purchase_date    = str(p_date),
                        supplier         = p_supplier,
                        product_name     = it["name"],
                        unit_price       = round(unit_price, 1),
                        quantity         = it["quantity"],
                        shipping         = round(ship_per_unit, 1),
                        tax_type         = p_tax,
                        total_unit_price = round(total_unit, 1),
                        note             = p_note,
                    )
                if not ok:
                    errors.append(f"{it['name'] or '（未入力）'}: {err_msg}")
            if errors:
                st.error("保存失敗:\n" + "\n".join(errors))
            else:
                st.success("✅ 修正を保存しました！" if is_edit else f"✅ {n_items} 件の仕入れを保存しました！")
                for k in ["purchase_items", "p_date", "p_supplier", "p_tax", "p_shipping",
                           "p_note", "p_edit_page_ids", "p_item_rev"]:
                    st.session_state.pop(k, None)
                st.rerun()

        # ── 保存済み仕入れ記録 ───────────────────────────
        st.markdown("---")
        st.markdown("**📋 保存済み仕入れ記録（直近20件）**")
        purchase_logs = load_purchase_records(limit=20)
        if purchase_logs:
            # 仕入日＋取引先でグループ化（順序保持）
            _groups: dict[str, list] = {}
            for r in purchase_logs:
                _key = f"{r['purchase_date']}||{r['supplier']}"
                _groups.setdefault(_key, []).append(r)

            for _gkey, _rows in _groups.items():
                _first = _rows[0]
                # グループヘッダー行（仕入日・取引先・商品数・修正ボタン）
                hc1, hc2, hc3, hc4 = st.columns([2, 3, 2, 1])
                hc1.markdown(f"**{_first['purchase_date']}**")
                hc2.markdown(f"**{_first['supplier']}**")
                hc3.caption(f"{len(_rows)} 商品")
                if hc4.button("✏️ 修正", key=f"edit_g_{_gkey}"):
                    st.session_state["p_edit_page_ids"] = [r["page_id"] for r in _rows]
                    st.session_state["p_date_pre"]     = _first["purchase_date"]
                    st.session_state["p_supplier_pre"] = _first["supplier"]
                    st.session_state["p_tax_pre"]      = _first["tax_type"]
                    st.session_state["p_shipping_pre"] = float(_first["shipping"]) * len(_rows)
                    st.session_state["p_note_pre"]     = _first["note"]
                    st.session_state["purchase_items"] = [
                        {"name": r["product_name"],
                         "total_price": float(r["unit_price"]) * int(r["quantity"]),
                         "quantity": int(r["quantity"])}
                        for r in _rows
                    ]
                    # リビジョンを上げてウィジェットキーを完全に切り替える
                    st.session_state["p_item_rev"] = st.session_state.get("p_item_rev", 0) + 1
                    st.session_state["_scroll_top"] = True
                    st.rerun()
                # 商品詳細（インデントして表示）
                for r in _rows:
                    dc1, dc2, dc3 = st.columns([4, 2, 2])
                    dc1.caption(f"　{r['product_name']}")
                    dc2.caption(f"送料込み商品単価 ¥{r['total_unit_price']:.1f}")
                    dc3.caption(f"{r['quantity']}個")
                st.markdown("---")
        else:
            st.caption("まだ仕入れ記録がありません。")

    if reg_sub == "💴 決まった売値の登録":
        # ── 決まった売値の登録 ──────────────────────────
        _do_dec_scroll = st.session_state.pop("_dec_scroll", False)
        st.subheader("💴 決まった売値の登録")
        st.caption("売値・ルールなどチームの決め事を記録してAI勘ちゃんが参照します。")

        # プリセットキー → ウィジェットキーへ転送（widget描画前に行うことでエラーを回避）
        for _f, _t in [("dec_item_pre","dec_item"),("dec_qty_pre","dec_qty"),
                       ("dec_price_pre","dec_price"),("dec_note_pre","dec_note")]:
            if _f in st.session_state:
                st.session_state[_t] = st.session_state.pop(_f)

        # session_state キー初期化
        for _k in ("dec_item","dec_qty","dec_price","dec_note"):
            if _k not in st.session_state:
                st.session_state[_k] = ""

        # 選択後スクロール： window.parent.scrollTo で固定Y座標へ移動
        _DEC_SCROLL_Y = 600  # ← ずれる場合はこの値を調整（px）
        if _do_dec_scroll:
            _components.html(f"""<script>
              setTimeout(function(){{
                window.parent.scrollTo({{top: {_DEC_SCROLL_Y}, behavior: 'smooth'}});
              }}, 300);
            </script>""", height=0)

        # 仕入れ済み商品から選ぶ
        with st.expander("📋 仕入れ済み商品から選ぶ", expanded=False):
            purchase_recs = load_purchase_records(limit=30)
            if purchase_recs:
                for rec in purchase_recs:
                    c1, c2, c3, c4, c5 = st.columns([2, 2, 3, 2, 1])
                    c1.caption(rec["purchase_date"])
                    c2.caption(rec["supplier"])
                    c3.caption(rec["product_name"])
                    c4.caption(f"¥{rec['total_unit_price']:.1f}")
                    if c5.button("選択", key=f"sel_{rec['page_id']}"):
                        st.session_state["dec_item_pre"] = rec["product_name"]
                        st.session_state["_dec_scroll"] = True
                        st.rerun()
            else:
                st.caption("まだ仕入れ記録がありません。")

        dec_item  = st.text_input("品物名",      key="dec_item",  placeholder="例：ネーブルオレンジ")
        dec_qty   = st.text_input("量",          key="dec_qty",   placeholder="例：1個、1kg、1箱")
        dec_price = st.text_input("売値（円）",   key="dec_price", placeholder="例：500円")
        dec_note  = st.text_input("備考（任意）", key="dec_note",  placeholder="例：パンダ広場・いきいき共通")

        dec_edit_page_id = st.session_state.get("dec_edit_page_id")
        if dec_edit_page_id:
            st.info("✏️ 修正モード：上書き保存されます")

        if st.button("💾 修正を保存する" if dec_edit_page_id else "💾 保存する", key="dec_save"):
            if dec_item and dec_price:
                if dec_edit_page_id:
                    ok = update_accounting_decision(dec_edit_page_id, dec_item, dec_qty, dec_price, dec_note)
                else:
                    ok = save_accounting_decision(dec_item, "🏷️ 売値", dec_qty, dec_price, dec_note)
                if ok:
                    st.success("✅ 修正を保存しました！" if dec_edit_page_id else "✅ 決め事を保存しました！")
                    for k in ("dec_item", "dec_qty", "dec_price", "dec_note", "dec_edit_page_id"):
                        st.session_state.pop(k, None)
                    st.rerun()
                else:
                    st.error("保存に失敗しました。Notion設定を確認してください。")
            else:
                st.warning("品物名と金額は必須です。")

        decisions = load_accounting_decisions()
        if decisions:
            st.markdown("**📋 登録済みの決め事**")
            for d in decisions:
                qty  = f"　{d['quantity']}" if d.get("quantity") else ""
                note = f"　（{d['note']}）" if d.get("note") else ""
                c1, c2 = st.columns([8, 1])
                c1.markdown(f"**{d['item_name']}**{qty}　→　{d['price']}{note}")
                if c2.button("✏️", key=f"edit_d_{d['page_id']}"):
                    st.session_state["dec_edit_page_id"] = d["page_id"]
                    st.session_state["dec_item_pre"]  = d["item_name"]
                    st.session_state["dec_qty_pre"]   = d["quantity"]
                    st.session_state["dec_price_pre"] = d["price"]
                    st.session_state["dec_note_pre"]  = d["note"]
                    st.rerun()
        else:
            st.caption("まだ決め事が登録されていません。")

