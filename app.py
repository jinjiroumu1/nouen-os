import streamlit as st
from db.database import init_db

init_db()

st.set_page_config(
    page_title="田心ジンジャー",
    page_icon="🫚",
    layout="wide",
)

st.title("🫚 田心ジンジャー")
st.markdown("---")

st.markdown("""
### 育てる。食べる。学ぶ。記録する。循環する。

AI−勘ちゃんは、田心ジンジャーの記憶をつなぐ伴走者です。

---

**サイドバーから各機能へ進んでください。**

| ページ | 説明 |
|---|---|
| 🌿 農業日誌 | 天候・作業・気づきを記録する |
| 📅 栽培計画 | 月別の栽培スケジュールを管理する |
| 🍳 料理 | 収穫物からレシピを記録・探す |
| 💬 チャット | 日々の疑問をAI勘ちゃんと対話する |
| 🕸️ ネットワーク図 | 知識のつながりを可視化する |
| 💰 会計・原価管理 | 販売・原価・支払いをAI勘ちゃんと確認する |
""")

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("知識の色分け", "創発知", "🌸 pink")
with col2:
    st.metric("", "賢人知", "💙 blue")
with col3:
    st.metric("", "重なった知", "💜 purple")
with col4:
    st.metric("", "数値データ", "🩶 gray")

st.caption("AIは伴走者です。最終判断は人間が行います。")
