import streamlit as st


def render_mermaid(code: str):
    """Mermaidコードをstreamlit上でHTMLレンダリングする"""
    html = f"""
    <div class="mermaid" style="background:white;padding:1rem;border-radius:8px;">
    {code}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true}});</script>
    """
    st.components.v1.html(html, height=500, scrolling=True)


def nodes_edges_to_mermaid(nodes: list[dict], edges: list[dict]) -> str:
    """NetworkNodes/Edgesリストから Mermaid graph LR コードを生成する"""
    COLOR_MAP = {
        "souhatsuchi": "#ffb6c1",   # pink
        "kenjinchi": "#add8e6",     # blue
        "kasanatta": "#d8b4fe",     # purple
        "suuchi": "#d1d5db",        # gray
    }

    lines = ["graph LR"]

    for node in nodes:
        label = node.get("label", "")
        nid = label.replace(" ", "_")
        color = COLOR_MAP.get(node.get("source_type", ""), "#ffffff")
        lines.append(f'    {nid}["{label}"]')
        lines.append(f'    style {nid} fill:{color}')

    for edge in edges:
        f = edge.get("from_node", "").replace(" ", "_")
        t = edge.get("to_node", "").replace(" ", "_")
        rel = edge.get("relationship", "")
        lines.append(f'    {f} -->|"{rel}"| {t}')

    return "\n".join(lines)
