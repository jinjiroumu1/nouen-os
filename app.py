import streamlit as st
from pathlib import Path
from db.database import init_db

init_db()

# ── Google OAuth コールバック処理（リダイレクトURIがベースURLのため app.py で受け取る） ──
_params = st.query_params
if "code" in _params and "google_oauth_creds" not in st.session_state:
    try:
        # 07_POP.py で生成・保存したflowオブジェクトを使い回す（code_verifier一致のため）
        _flow = st.session_state.get("_gdrive_flow")
        if _flow is None:
            st.error("認証フローが見つかりません。もう一度「Googleアカウントで認証する」を押してください。")
        else:
            _flow.fetch_token(code=_params["code"])
            _creds = _flow.credentials
            st.session_state["google_oauth_creds"] = {
                "token":         _creds.token,
                "refresh_token": _creds.refresh_token,
                "token_uri":     _creds.token_uri,
                "client_id":     _creds.client_id,
                "client_secret": _creds.client_secret,
                "scopes":        list(_creds.scopes) if _creds.scopes else [],
            }
            st.session_state.pop("_gdrive_flow", None)
            st.query_params.clear()
            st.switch_page("pages/07_POP.py")
    except Exception as _e:
        st.error(f"Google認証エラー: {_e}")

st.set_page_config(
    page_title="田心ジンジャー",
    page_icon="🫚",
    layout="wide",
)

# ── ヘッダー画像 ──────────────────────────────────────────
img_path = Path("docs/tajin_ginger_team.png")
if img_path.exists():
    col_l, col_c, col_r = st.columns([1, 3, 1])
    with col_c:
        st.image(str(img_path), use_container_width=True)

# ── タイトル ──────────────────────────────────────────────
st.title("🫚 田心ジンジャー")
st.markdown("---")

st.markdown("""
### 育てる。食べる。学ぶ。記録する。循環する。

AI−勘ちゃんは、田心ジンジャーの記憶をつなぐ伴走者です。

---
""")

# ── メニュー表 ────────────────────────────────────────────
st.markdown("""
| ページ | キャラクター | 説明 |
|---|---|---|
| 🌿 農業日誌 | 徒然ジンジャー（赤） | 天候・作業・気づきを記録する |
| 📅 栽培計画 | ポップジンジャー（紫） | 月別の栽培スケジュールを管理する |
| 🍳 料理 | 緑ジンジャー（緑） | 収穫物からレシピを記録・探す |
| 💬 チャット | 御伽ジンジャー（黄） | 日々の疑問をAI勘ちゃんと対話する |
| 🕸️ ネットワーク図 | 忍者ジンジャー（ピンク） | 知識のつながりを可視化する |
| 💰 会計・原価管理 | プライスジンジャー（青） | 販売・原価・支払いをAI勘ちゃんと確認する |
""")

st.markdown("---")

# ── 知識の色分け ──────────────────────────────────────────
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
