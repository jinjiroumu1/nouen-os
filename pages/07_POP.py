import base64
import streamlit as st
from pathlib import Path
from utils.pop_loader import load_pop_files

st.set_page_config(page_title="POP", page_icon="🪧", layout="wide")

_img = Path("docs/characters/pop.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)

st.title("🪧 POP")
st.caption("商品POPをGoogle Driveから検索・ダウンロードする")

# ── ファイル取得 ──────────────────────────────────────────
with st.spinner("Google DriveからPOPファイルを読み込み中…"):
    files = load_pop_files()

if not files:
    st.info(
        "POPファイルが見つかりません。\n"
        "Streamlit Cloud の Secrets に `POP_FOLDER_ID` を追加し、\n"
        "Google Drive フォルダをサービスアカウントと共有してください。\n\n"
        "サービスアカウント: `nouen-os-drive@electric-wave-500502-n2.iam.gserviceaccount.com`"
    )
    st.stop()

st.success(f"{len(files)} 件のPOPファイルを読み込みました")

# ── 検索 ─────────────────────────────────────────────────
query = st.text_input("🔍 商品名で検索", placeholder="例：しょうが　なす　ジンジャー")

if query:
    results = [f for f in files if query.lower() in f["name"].lower()]
else:
    results = files

st.markdown(f"**{len(results)} 件**")
st.markdown("---")

# ── 一覧表示 ──────────────────────────────────────────────
for f in results:
    col_name, col_dl = st.columns([5, 1])

    with col_name:
        if f["mime"].startswith("image/"):
            with st.expander(f"🖼️ {f['name']}"):
                img_bytes = base64.b64decode(f["data"])
                st.image(img_bytes, use_container_width=True)
        else:
            st.markdown(f"📄 **{f['name']}**")

    with col_dl:
        ext = f["name"].rsplit(".", 1)[-1] if "." in f["name"] else "bin"
        mime = f["mime"]
        st.download_button(
            label="⬇️",
            data=base64.b64decode(f["data"]),
            file_name=f["name"],
            mime=mime,
            key=f"dl_{f['name']}",
        )
