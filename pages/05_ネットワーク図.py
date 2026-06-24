import streamlit as st
import pandas as pd
from db.database import get_connection
from utils.mermaid import render_mermaid, nodes_edges_to_mermaid
from utils.ai_advisor import (
    get_ai_response_network,
    extract_nodes_and_edges,
    get_node_explanation,
    SOURCE_TYPE_LABEL,
)

st.set_page_config(page_title="ネットワーク図", page_icon="🕸️", layout="wide")
st.title("🕸️ ネットワーク図")
st.caption("会話と行動から生まれた概念の地図。🌸創発知 💙賢人知 💜重なった知 🩶数値")

# ── セッション初期化 ───────────────────────────────────────
if "net_question" not in st.session_state:
    st.session_state.net_question = ""
if "net_answer" not in st.session_state:
    st.session_state.net_answer = ""
if "net_candidates" not in st.session_state:
    st.session_state.net_candidates = {"nodes": [], "edges": []}
if "net_approved_nodes" not in st.session_state:
    st.session_state.net_approved_nodes = []
if "net_approved_edges" not in st.session_state:
    st.session_state.net_approved_edges = []

tab1, tab2, tab3, tab4 = st.tabs(["💬 チャット→ノード抽出", "✅ 候補を承認", "🔍 ノード解説", "🗺️ 図を見る"])

# ────────────────────────────────────────────────────────────
# Tab1: チャット → 自動ノード抽出
# ────────────────────────────────────────────────────────────
with tab1:
    st.subheader("AI勘ちゃんに聞く → 概念を抽出する")
    st.caption("会話に登場した概念だけがノードになります。書籍全体はノード化しません。")

    with st.form("network_chat_form"):
        question = st.text_area("問い・話題", placeholder="例：野菜に必要な栄養素は何？\n例：夏の茄子を使った料理は？")
        submitted = st.form_submit_button("勘ちゃんに聞く＆ノード抽出")

    if submitted and question:
        with st.spinner("AI勘ちゃんが考えています…"):
            answer = get_ai_response_network(question, [])
        st.session_state.net_question = question
        st.session_state.net_answer   = answer

        with st.spinner("概念を抽出しています…"):
            candidates = extract_nodes_and_edges(question, answer)
        st.session_state.net_candidates     = candidates
        st.session_state.net_approved_nodes = []
        st.session_state.net_approved_edges = []
        st.rerun()

    if st.session_state.net_answer:
        with st.chat_message("user", avatar="👨‍🌾"):
            st.markdown(st.session_state.net_question)
        with st.chat_message("assistant", avatar="🌱"):
            st.markdown(st.session_state.net_answer)

        st.markdown("---")
        st.subheader("📌 抽出されたノード・エッジ候補")
        st.caption("「✅ 候補を承認」タブで選んでDBに追加できます。")

        candidates = st.session_state.net_candidates
        if candidates.get("nodes"):
            st.markdown("**ノード候補：**")
            for n in candidates["nodes"]:
                label = SOURCE_TYPE_LABEL.get(n.get("source_type", ""), "")
                st.markdown(f"- {label} **{n['label']}**")
        if candidates.get("edges"):
            st.markdown("**エッジ候補：**")
            for e in candidates["edges"]:
                st.markdown(f"- {e['from_node']} → {e['to_node']}（{e.get('relationship','')}）")

# ────────────────────────────────────────────────────────────
# Tab2: 候補を承認してDBに追加
# ────────────────────────────────────────────────────────────
with tab2:
    st.subheader("候補を確認して承認する")
    st.caption("チェックしたものだけDBに追加されます。最終判断は人間が行います。")

    candidates = st.session_state.net_candidates
    nodes_c = candidates.get("nodes", [])
    edges_c = candidates.get("edges", [])

    if not nodes_c:
        st.info("まずTab1でチャットして候補を生成してください。")
    else:
        st.markdown("**ノード候補：**")
        approved_nodes = []
        for i, n in enumerate(nodes_c):
            label = SOURCE_TYPE_LABEL.get(n.get("source_type", ""), "")
            checked = st.checkbox(f"{label} {n['label']}", key=f"node_{i}", value=True)
            if checked:
                approved_nodes.append(n)

        st.markdown("**エッジ候補：**")
        approved_edges = []
        for i, e in enumerate(edges_c):
            checked = st.checkbox(
                f"{e['from_node']} → {e['to_node']}（{e.get('relationship','')}）",
                key=f"edge_{i}", value=True,
            )
            if checked:
                approved_edges.append(e)

        if st.button("✅ 選択したものをDBに追加", type="primary"):
            COLOR_MAP = {"souhatsuchi": "pink", "kenjinchi": "blue",
                         "kasanatta": "purple", "suuchi": "gray"}
            conn = get_connection()

            # 既存ノードを取得して重複チェック
            existing = {r["label"] for r in conn.execute(
                "SELECT label FROM network_nodes").fetchall()}

            added_nodes = []
            for n in approved_nodes:
                if n["label"] not in existing:
                    st._source_type = n.get("source_type", "souhatsuchi")
                    conn.execute(
                        "INSERT INTO network_nodes (label, type, source_type, color) VALUES (?,?,?,?)",
                        (n["label"], "", n.get("source_type", "souhatsuchi"),
                         COLOR_MAP.get(n.get("source_type", ""), "pink")),
                    )
                    added_nodes.append(n["label"])

            for e in approved_edges:
                conn.execute(
                    "INSERT INTO network_edges (from_node, to_node, relationship, weight) VALUES (?,?,?,?)",
                    (e["from_node"], e["to_node"], e.get("relationship", ""), 1),
                )

            conn.commit()
            conn.close()

            st.success(f"追加しました。ノード：{len(added_nodes)}個　エッジ：{len(approved_edges)}個")
            if added_nodes:
                st.info(f"追加されたノード：{', '.join(added_nodes)}")
            st.session_state.net_candidates = {"nodes": [], "edges": []}
            st.rerun()

# ────────────────────────────────────────────────────────────
# Tab3: ノード解説（過去の会話を検索）
# ────────────────────────────────────────────────────────────
with tab3:
    st.subheader("ノードの解説を見る")
    st.caption("ノードをクリックすると、過去の農縁団の記録からその概念に関する会話を探します。")

    conn = get_connection()
    nodes = [dict(r) for r in conn.execute("SELECT * FROM network_nodes ORDER BY id DESC").fetchall()]
    conn.close()

    if not nodes:
        st.info("まだノードがありません。Tab1でチャットして追加してください。")
    else:
        COLOR_MAP_DISPLAY = {
            "souhatsuchi": "🌸", "kenjinchi": "💙",
            "kasanatta": "💜", "suuchi": "🩶",
        }
        node_labels = [
            f"{COLOR_MAP_DISPLAY.get(n['source_type'], '📌')} {n['label']}"
            for n in nodes
        ]
        selected = st.selectbox("ノードを選ぶ", node_labels)

        if selected and st.button("🔍 このノードの解説を見る"):
            node_label = selected.split(" ", 1)[-1]
            with st.spinner(f"「{node_label}」に関する過去の記録を検索しています…"):
                explanation = get_node_explanation(node_label)
            st.markdown("---")
            st.subheader(f"📖 「{node_label}」の解説")
            st.markdown(explanation)

# ────────────────────────────────────────────────────────────
# Tab4: 図を見る
# ────────────────────────────────────────────────────────────
with tab4:
    st.subheader("知恵の地図")

    conn = get_connection()
    nodes = [dict(r) for r in conn.execute("SELECT * FROM network_nodes").fetchall()]
    edges = [dict(r) for r in conn.execute("SELECT * FROM network_edges").fetchall()]
    conn.close()

    if not nodes:
        st.info("ノードがありません。Tab1でチャットして追加してください。")
    else:
        mermaid_code = nodes_edges_to_mermaid(nodes, edges)
        st.markdown("**グラフ**")
        render_mermaid(mermaid_code)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 ノードCSV",
                data=pd.DataFrame(nodes).to_csv(index=False, encoding="utf-8-sig"),
                file_name="network_nodes.csv", mime="text/csv",
            )
        with col2:
            st.download_button(
                "📥 エッジCSV",
                data=pd.DataFrame(edges).to_csv(index=False, encoding="utf-8-sig"),
                file_name="network_edges.csv", mime="text/csv",
            )

        st.markdown("---")
        st.markdown("**Mermaidコード**")
        st.code(mermaid_code, language="text")
