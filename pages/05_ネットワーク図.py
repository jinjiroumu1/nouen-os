import streamlit as st
from utils.mermaid import render_mermaid
from utils.ai_advisor import build_network_from_notion, SOURCE_TYPE_LABEL

st.set_page_config(page_title="ネットワーク図", page_icon="🕸️", layout="wide")
st.title("🕸️ ネットワーク図")
st.caption("われまち農縁団の対話と行動から生まれた概念の地図　🌸創発知 💙賢人知 💜重なった知 🩶数値")

# 更新ボタン
if st.button("🔄 図を更新する（Notionから再取得）"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")

# Notionデータから自動生成
with st.spinner("Notionの記録を読み込んで、知恵の地図を生成しています…"):
    network = build_network_from_notion()

nodes = network.get("nodes", [])
edges = network.get("edges", [])

if not nodes:
    st.info("まだNotionに記録がありません。農業日誌・料理・チャットを書き溜めると図が生成されます。")
else:
    # Mermaidコードを生成
    COLOR_MAP = {
        "souhatsuchi": "pink",
        "kenjinchi":   "lightblue",
        "kasanatta":   "plum",
        "suuchi":      "lightgray",
    }

    lines = ["graph LR"]
    # ノード定義（色付き）
    for n in nodes:
        label = n["label"].replace('"', "")
        node_id = label.replace(" ", "_").replace("・", "_").replace("、", "_")
        color = COLOR_MAP.get(n.get("source_type", "souhatsuchi"), "pink")
        lines.append(f'    {node_id}["{label}"]')
        lines.append(f'    style {node_id} fill:{color},stroke:#999,color:#333')

    # エッジ定義
    for e in edges:
        f_id = e["from_node"].replace(" ", "_").replace("・", "_").replace("、", "_")
        t_id = e["to_node"].replace(" ", "_").replace("・", "_").replace("、", "_")
        rel  = e.get("relationship", "")
        if rel:
            lines.append(f'    {f_id} -->|"{rel}"| {t_id}')
        else:
            lines.append(f'    {f_id} --> {t_id}')

    mermaid_code = "\n".join(lines)

    render_mermaid(mermaid_code)

    # 凡例
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown("🌸 **創発知**　現場・実感")
    col2.markdown("💙 **賢人知**　専門・基本書")
    col3.markdown("💜 **重なった知**　両方")
    col4.markdown("🩶 **数値データ**")

    # ノード一覧
    with st.expander("📋 ノード一覧を見る"):
        for n in nodes:
            label_icon = SOURCE_TYPE_LABEL.get(n.get("source_type", ""), "📌")
            st.markdown(f"- {label_icon} {n['label']}")
