import streamlit as st
from utils.mermaid import render_mermaid
from utils.ai_advisor import (
    build_network_from_notion,
    get_node_explanation,
    get_ai_response_network,
    SOURCE_TYPE_LABEL,
)

st.set_page_config(page_title="ネットワーク図", page_icon="🕸️", layout="wide")
st.title("🕸️ ネットワーク図")
st.caption("われまち農縁団の対話と行動から生まれた概念の地図　🌿創発知 💚賢人知 🍀重なった知 🪨数値")

COLOR_MAP = {
    "souhatsuchi": "#a8d5a2",   # 明るい緑（創発知）
    "kenjinchi":   "#4a9e6b",   # 深い緑（賢人知）
    "kasanatta":   "#c8e6c9",   # 薄い緑（重なった知）
    "suuchi":      "#b0bec5",   # グレー（数値）
}
TEXT_COLOR = {
    "souhatsuchi": "#1b4332",
    "kenjinchi":   "#ffffff",
    "kasanatta":   "#1b4332",
    "suuchi":      "#37474f",
}

if st.button("🔄 図を更新する（Notionから再取得）"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")

# ── Notionデータから自動生成 ───────────────────────────────
with st.spinner("Notionの記録を読み込んで、知恵の地図を生成しています…"):
    network = build_network_from_notion()

nodes = network.get("nodes", [])
edges = network.get("edges", [])

if not nodes:
    st.info("まだNotionに記録がありません。農業日誌・料理・チャットを書き溜めると図が生成されます。")
else:
    # ── Mermaidコード生成 ─────────────────────────────────
    lines = ["graph LR"]
    for n in nodes:
        label   = n["label"].replace('"', "").replace("'", "")
        node_id = (label.replace(" ", "_").replace("・", "_")
                        .replace("、", "_").replace("（", "_").replace("）", "_"))
        fill  = COLOR_MAP.get(n.get("source_type", "souhatsuchi"), "#a8d5a2")
        color = TEXT_COLOR.get(n.get("source_type", "souhatsuchi"), "#1b4332")
        lines.append(f'    {node_id}["{label}"]')
        lines.append(f'    style {node_id} fill:{fill},stroke:#388e3c,color:{color}')

    for e in edges:
        f_id = (e["from_node"].replace(" ", "_").replace("・", "_")
                              .replace("、", "_").replace("（", "_").replace("）", "_"))
        t_id = (e["to_node"].replace(" ", "_").replace("・", "_")
                            .replace("、", "_").replace("（", "_").replace("）", "_"))
        rel  = e.get("relationship", "")
        if rel:
            lines.append(f'    {f_id} -->|"{rel}"| {t_id}')
        else:
            lines.append(f'    {f_id} --> {t_id}')

    mermaid_code = "\n".join(lines)
    render_mermaid(mermaid_code)

    # 凡例
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown("🌿 **創発知**　現場・実感")
    col2.markdown("💚 **賢人知**　専門・基本書")
    col3.markdown("🍀 **重なった知**　両方")
    col4.markdown("🪨 **数値データ**")

    st.markdown("---")

    # ── ノードを選んで繋がりを深く見る ───────────────────
    st.subheader("🔍 ノードの繋がりを深く見る")
    st.caption("ノードを選ぶと、そのノードに繋がる概念と過去の記録が表示されます。")

    node_labels = [n["label"] for n in nodes]
    selected = st.selectbox("ノードを選ぶ", ["（選んでください）"] + node_labels)

    if selected and selected != "（選んでください）":
        # 選択ノードに繋がるエッジを抽出
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
            if connected_nodes:
                for cn in connected_nodes:
                    n_info = next((n for n in nodes if n["label"] == cn), {})
                    icon = SOURCE_TYPE_LABEL.get(n_info.get("source_type", ""), "📌")
                    st.markdown(f"- {icon} {cn}")
            else:
                st.markdown("（繋がりなし）")

        with col_b:
            st.markdown(f"**エッジ（関係）：**")
            for e in related_edges:
                st.markdown(f"- {e['from_node']} → {e['to_node']}　*{e.get('relationship','')}*")

        # 過去の記録から解説
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

    # 過去の対話を表示
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
