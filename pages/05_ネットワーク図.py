import streamlit as st
import streamlit.components.v1 as components
from utils.ai_advisor import (
    build_network_from_notion,
    get_node_explanation,
    get_ai_response_network,
    SOURCE_TYPE_LABEL,
    _fetch_db_records,
    RECIPE_DB_ID,
)

st.set_page_config(page_title="ネットワーク図", page_icon="🕸️", layout="wide")
st.title("🕸️ ネットワーク図")
st.caption("われまち農縁団の対話と行動から生まれた概念の地図　🌸創発知 💙賢人知 💜重なった知 🩶数値")

COLOR_MAP = {
    "souhatsuchi": "#FFB6C1",
    "kenjinchi":   "#87CEEB",
    "kasanatta":   "#DDA0DD",
    "suuchi":      "#D3D3D3",
}

if st.button("🔄 図を更新する（Notionから再取得）"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")

# ── Notionデータから自動生成 ───────────────────────────────
with st.spinner("Notionの記録を読み込んで、知恵の地図を生成しています…"):
    network = build_network_from_notion()

# ── デバッグ ──────────────────────────────────────────────
with st.expander("🔧 デバッグ（確認用）"):
    recipe_raw = _fetch_db_records(RECIPE_DB_ID, limit=5)
    st.text(recipe_raw)
    st.markdown("---")
    st.text(f"nodes: {len(network.get('nodes', []))}　edges: {len(network.get('edges', []))}")
    if "_debug" in network:
        st.text(network["_debug"])

nodes = network.get("nodes", [])
edges = network.get("edges", [])

if not nodes:
    st.info("まだNotionに記録がありません。農業日誌・料理・チャットを書き溜めると図が生成されます。")
else:
    # ── pyvisでインタラクティブネットワーク図 ─────────────
    try:
        from pyvis.network import Network

        # エッジ数からノードサイズを計算
        edge_count: dict[str, int] = {}
        for e in edges:
            edge_count[e.get("from_node", "")] = edge_count.get(e.get("from_node", ""), 0) + 1
            edge_count[e.get("to_node", "")]   = edge_count.get(e.get("to_node", ""), 0) + 1

        net = Network(height="600px", width="100%", bgcolor="#f8f9fa", font_color="#333333")
        net.set_options("""{
            "physics": {
                "enabled": true,
                "stabilization": {"iterations": 100}
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 200
            },
            "edges": {
                "smooth": {"type": "curvedCW", "roundness": 0.2}
            }
        }""")

        for n in nodes:
            label      = n["label"]
            color      = COLOR_MAP.get(n.get("source_type", "souhatsuchi"), "#FFB6C1")
            size       = 20 + edge_count.get(label, 0) * 5
            source_lbl = SOURCE_TYPE_LABEL.get(n.get("source_type", ""), "")
            net.add_node(
                label,
                label=label,
                color=color,
                size=size,
                title=f"{source_lbl}　{label}",
                font={"size": 14},
            )

        for e in edges:
            net.add_edge(
                e["from_node"],
                e["to_node"],
                title=e.get("relationship", ""),
                label=e.get("relationship", ""),
                font={"size": 10, "align": "middle"},
                arrows="to",
            )

        html_str = net.generate_html()
        components.html(html_str, height=620, scrolling=False)

    except ImportError:
        st.warning("pyvisがインストールされていません。requirements.txtを確認してください。")

    # 凡例
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown("🌸 **創発知**　現場・実感")
    col2.markdown("💙 **賢人知**　専門・基本書")
    col3.markdown("💜 **重なった知**　両方")
    col4.markdown("🩶 **数値データ**")

    st.markdown("---")

    # ── ノードを選んで繋がりを深く見る ───────────────────
    st.subheader("🔍 ノードの繋がりを深く見る")
    node_labels = [n["label"] for n in nodes]
    selected = st.selectbox("ノードを選ぶ", ["（選んでください）"] + node_labels)

    if selected and selected != "（選んでください）":
        related_edges = [
            e for e in edges
            if e["from_node"] == selected or e["to_node"] == selected
        ]
        connected_nodes = set()
        for e in related_edges:
            connected_nodes.add(e["from_node"])
            connected_nodes.add(e["to_node"])
        connected_nodes.discard(selected)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**「{selected}」に繋がる概念：**")
            for cn in connected_nodes:
                n_info = next((n for n in nodes if n["label"] == cn), {})
                icon = SOURCE_TYPE_LABEL.get(n_info.get("source_type", ""), "📌")
                st.markdown(f"- {icon} {cn}")

        with col_b:
            st.markdown("**エッジ（関係）：**")
            for e in related_edges:
                st.markdown(f"- {e['from_node']} → {e['to_node']}　*{e.get('relationship','')}*")

        with st.spinner(f"「{selected}」に関する過去の記録を検索中…"):
            explanation = get_node_explanation(selected)
        st.markdown("---")
        st.markdown(f"**📖 「{selected}」の解説（過去の記録より）**")
        st.markdown(explanation)

    st.markdown("---")

    # ── ネットワーク図へのチャット ────────────────────────
    st.subheader("💬 ネットワーク図に質問する")
    st.caption("図の中の概念や繋がりについて、勘ちゃんに聞けます。")

    if "net_chat_hist" not in st.session_state:
        st.session_state.net_chat_hist = []

    for msg in st.session_state.net_chat_hist:
        avatar = "👨‍🌾" if msg["role"] == "user" else "🌱"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    user_input = st.chat_input("ネットワーク図について質問する（例：土壌と窒素はどう繋がっている？）")
    if user_input:
        st.session_state.net_chat_hist.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👨‍🌾"):
            st.markdown(user_input)
        with st.spinner("勘ちゃんが考えています…"):
            reply = get_ai_response_network(user_input, st.session_state.net_chat_hist[:-1])
        st.session_state.net_chat_hist.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant", avatar="🌱"):
            st.markdown(reply)

    if st.session_state.net_chat_hist and st.button("チャットをリセット"):
        st.session_state.net_chat_hist = []
        st.rerun()

    # ノード一覧
    with st.expander("📋 ノード一覧"):
        for n in nodes:
            icon = SOURCE_TYPE_LABEL.get(n.get("source_type", ""), "📌")
            st.markdown(f"- {icon} {n['label']}")
