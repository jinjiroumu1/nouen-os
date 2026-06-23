import streamlit as st
import pandas as pd
from db.database import get_connection
from utils.mermaid import render_mermaid, nodes_edges_to_mermaid

st.set_page_config(page_title="ネットワーク図", page_icon="🕸️", layout="wide")
st.title("🕸️ ネットワーク図")
st.caption("知識のつながりを可視化する。色：🌸創発知 💙賢人知 💜重なった知 🩶数値")

tab1, tab2, tab3 = st.tabs(["ノード追加", "エッジ追加", "図を見る"])

# ── ノード追加 ─────────────────────────────────────────────
with tab1:
    with st.form("node_form"):
        label = st.text_input("ノード名", placeholder="例：トマト、コンパニオンプランツ")
        node_type = st.text_input("種類", placeholder="例：作物、技術、場所")
        source_type = st.selectbox(
            "知識の種別",
            ["souhatsuchi", "kenjinchi", "kasanatta", "suuchi"],
            format_func=lambda x: {"souhatsuchi": "🌸 創発知", "kenjinchi": "💙 賢人知",
                                   "kasanatta": "💜 重なった知", "suuchi": "🩶 数値データ"}[x],
        )
        COLOR_MAP = {"souhatsuchi": "pink", "kenjinchi": "blue",
                     "kasanatta": "purple", "suuchi": "gray"}
        submitted = st.form_submit_button("ノードを追加")
        if submitted and label:
            conn = get_connection()
            conn.execute(
                "INSERT INTO network_nodes (label, type, source_type, color) VALUES (?,?,?,?)",
                (label, node_type, source_type, COLOR_MAP[source_type]),
            )
            conn.commit()
            conn.close()
            st.success(f"ノード「{label}」を追加しました。")
            st.rerun()

    st.markdown("#### 登録済みノード")
    conn = get_connection()
    nodes = [dict(r) for r in conn.execute("SELECT * FROM network_nodes").fetchall()]
    conn.close()
    if nodes:
        st.dataframe(pd.DataFrame(nodes), use_container_width=True)
    else:
        st.info("まだノードがありません。")

# ── エッジ追加 ─────────────────────────────────────────────
with tab2:
    conn = get_connection()
    nodes = [dict(r) for r in conn.execute("SELECT * FROM network_nodes").fetchall()]
    conn.close()

    if len(nodes) < 2:
        st.info("エッジを作るにはノードが2つ以上必要です。まずノードを追加してください。")
    else:
        node_labels = [n["label"] for n in nodes]
        with st.form("edge_form"):
            col1, col2 = st.columns(2)
            with col1:
                from_node = st.selectbox("from（起点）", node_labels)
            with col2:
                to_node = st.selectbox("to（終点）", node_labels)
            relationship = st.text_input("関係", placeholder="例：コンパニオン、収穫→料理")
            weight = st.slider("重み", 1, 5, 1)
            submitted = st.form_submit_button("エッジを追加")
            if submitted:
                conn = get_connection()
                conn.execute(
                    "INSERT INTO network_edges (from_node, to_node, relationship, weight) VALUES (?,?,?,?)",
                    (from_node, to_node, relationship, weight),
                )
                conn.commit()
                conn.close()
                st.success("エッジを追加しました。")
                st.rerun()

    st.markdown("#### 登録済みエッジ")
    conn = get_connection()
    edges = [dict(r) for r in conn.execute("SELECT * FROM network_edges").fetchall()]
    conn.close()
    if edges:
        st.dataframe(pd.DataFrame(edges), use_container_width=True)
    else:
        st.info("まだエッジがありません。")

# ── 図を見る ───────────────────────────────────────────────
with tab3:
    conn = get_connection()
    nodes = [dict(r) for r in conn.execute("SELECT * FROM network_nodes").fetchall()]
    edges = [dict(r) for r in conn.execute("SELECT * FROM network_edges").fetchall()]
    conn.close()

    if not nodes:
        st.info("ノードがありません。まず「ノード追加」タブでノードを登録してください。")
    else:
        mermaid_code = nodes_edges_to_mermaid(nodes, edges)

        st.markdown("**Mermaid コード**")
        st.code(mermaid_code, language="text")

        st.markdown("**グラフ**")
        render_mermaid(mermaid_code)

        st.markdown("---")
        st.download_button(
            "📥 ノードをCSVでダウンロード",
            data=pd.DataFrame(nodes).to_csv(index=False, encoding="utf-8-sig"),
            file_name="network_nodes.csv",
            mime="text/csv",
        )
        st.download_button(
            "📥 エッジをCSVでダウンロード",
            data=pd.DataFrame(edges).to_csv(index=False, encoding="utf-8-sig"),
            file_name="network_edges.csv",
            mime="text/csv",
        )
