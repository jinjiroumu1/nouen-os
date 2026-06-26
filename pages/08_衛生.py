import streamlit as st
from datetime import date, datetime, timedelta
from pathlib import Path
from utils.notion_sync import save_expiry_item, load_expiry_items, delete_expiry_item

st.set_page_config(page_title="衛生管理", page_icon="🧹", layout="wide")

_img = Path("docs/characters/clean.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)

st.title("🧹 衛生管理")
st.caption("食材・資材の賞味期限を管理する")

# ── 入力フォーム ──────────────────────────────────────────
with st.expander("➕ 商品を追加", expanded=True):
    with st.form("expiry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            product_name     = st.text_input("商品名 *", placeholder="例：豆腐、めんつゆ")
            expiry_date      = st.date_input("賞味期限 *", value=date.today())
            quantity         = st.text_input("数量", placeholder="例：3個、500g")
        with col2:
            storage_location = st.text_input("保管場所", placeholder="例：冷蔵庫・常温棚")
            note             = st.text_area("備考", placeholder="開封済み・未開封など", height=100)

        submitted = st.form_submit_button("💾 Notionに保存", use_container_width=True)
        if submitted:
            if not product_name:
                st.error("商品名を入力してください。")
            else:
                ok = save_expiry_item(
                    product_name,
                    str(expiry_date),
                    quantity,
                    storage_location,
                    note,
                )
                if ok:
                    st.success(f"「{product_name}」を保存しました！")
                    st.rerun()

st.markdown("---")

# ── 一覧表示 ──────────────────────────────────────────────
st.subheader("📋 賞味期限一覧")

if st.button("🔄 一覧を更新"):
    st.rerun()

with st.spinner("Notionから読み込み中…"):
    items = load_expiry_items()

if not items:
    st.info("登録された商品がありません。上のフォームから追加してください。")
    st.stop()

today = date.today()

def _sort_key(item):
    d = item.get("expiry_date", "")
    if not d:
        return date(9999, 12, 31)
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").date()
    except Exception:
        return date(9999, 12, 31)

items_sorted = sorted(items, key=_sort_key)

# 集計バッジ
expired  = [i for i in items_sorted if _sort_key(i) < today]
warning  = [i for i in items_sorted if today <= _sort_key(i) <= today + timedelta(days=3)]
safe     = [i for i in items_sorted if _sort_key(i) > today + timedelta(days=3)]

c1, c2, c3 = st.columns(3)
c1.metric("🔴 期限切れ", f"{len(expired)} 件")
c2.metric("🟡 3日以内", f"{len(warning)} 件")
c3.metric("🟢 安全", f"{len(safe)} 件")

st.markdown("---")

for item in items_sorted:
    exp = _sort_key(item)
    delta = (exp - today).days

    if exp < today:
        icon  = "🔴"
        label = f"**{abs(delta)}日超過**"
        color = "#ffcccc"
    elif delta <= 3:
        icon  = "🟡"
        label = f"あと **{delta}日**"
        color = "#fff8cc"
    else:
        icon  = "🟢"
        label = f"あと {delta}日"
        color = "#ccffcc"

    with st.container():
        st.markdown(
            f"""<div style="background:{color};padding:10px 14px;border-radius:8px;margin-bottom:8px;">
            {icon} <b>{item['product_name']}</b>
            📅 {item['expiry_date'][:10] if item['expiry_date'] else '不明'}　{label}
            {'📦 ' + item['quantity'] if item['quantity'] else ''}
            {'📍 ' + item['storage_location'] if item['storage_location'] else ''}
            {'📝 ' + item['note'] if item['note'] else ''}
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button("削除", key=f"del_{item['id']}"):
            delete_expiry_item(item["id"])
            st.rerun()
