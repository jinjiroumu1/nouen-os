import streamlit as st

SOURCE_COLORS = {
    "souhatsuchi": ("#fff0f3", "🌸", "創発知"),
    "kenjinchi":   ("#eff6ff", "💙", "賢人知"),
    "kasanatta":   ("#faf5ff", "💜", "重なった知"),
    "suuchi":      ("#f3f4f6", "🩶", "数値データ"),
}


def knowledge_card(title: str, body: str, source_type: str = "souhatsuchi"):
    bg, icon, label = SOURCE_COLORS.get(source_type, ("#ffffff", "📝", source_type))
    st.markdown(
        f"""
        <div style="background:{bg};border-radius:8px;padding:12px 16px;margin:8px 0;">
            <span style="font-size:0.75rem;opacity:0.6;">{icon} {label}</span>
            <div style="font-weight:600;margin:4px 0;">{title}</div>
            <div style="font-size:0.9rem;white-space:pre-wrap;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
