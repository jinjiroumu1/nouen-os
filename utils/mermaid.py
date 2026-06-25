import re
import streamlit as st


def _node_id(label: str) -> str:
    """ノードIDとして使える文字列に変換（英数字・アンダースコアのみ）"""
    # 日本語・特殊文字をアンダースコアに置換
    s = re.sub(r'[^\w]', '_', label, flags=re.UNICODE)
    # 先頭が数字の場合はプレフィックスを付ける
    if s and s[0].isdigit():
        s = "n_" + s
    # 連続するアンダースコアを1つに
    s = re.sub(r'_+', '_', s).strip('_')
    return s or "node"


def _escape_label(label: str) -> str:
    """Mermaidのノードラベル内でダブルクォートをエスケープ"""
    return label.replace('"', "'")


def _escape_edge(rel: str) -> str:
    """Mermaidのエッジラベル内で使えない文字をエスケープ"""
    # ダブルクォートとパイプ文字を除去
    return rel.replace('"', "'").replace('|', '｜')


def render_mermaid(code: str):
    """MermaidコードをStreamlit上でHTMLレンダリングする"""
    html = f"""
    <div class="mermaid" style="background:white;padding:1rem;border-radius:8px;overflow:auto;">
    {code}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>
      mermaid.initialize({{startOnLoad:true, securityLevel:'loose'}});
    </script>
    """
    st.components.v1.html(html, height=600, scrolling=True)


def nodes_edges_to_mermaid(nodes: list[dict], edges: list[dict]) -> str:
    """NetworkNodes/Edgesリストから Mermaid graph LR コードを生成する"""
    COLOR_MAP = {
        "souhatsuchi": "#ffb6c1",
        "kenjinchi":   "#add8e6",
        "kasanatta":   "#d8b4fe",
        "suuchi":      "#d1d5db",
    }

    lines = ["graph LR"]

    for node in nodes:
        label = node.get("label", "")
        nid   = _node_id(label)
        color = COLOR_MAP.get(node.get("source_type", ""), "#ffffff")
        lines.append(f'    {nid}["{_escape_label(label)}"]')
        lines.append(f'    style {nid} fill:{color},stroke:#999')

    for edge in edges:
        f_label = edge.get("from_node", "")
        t_label = edge.get("to_node", "")
        f_id = _node_id(f_label)
        t_id = _node_id(t_label)
        rel  = _escape_edge(edge.get("relationship", ""))
        if rel:
            lines.append(f'    {f_id} -->|"{rel}"| {t_id}')
        else:
            lines.append(f'    {f_id} --> {t_id}')

    code = "\n".join(lines)
    return code
