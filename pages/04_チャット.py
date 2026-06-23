import streamlit as st
from db.database import get_connection
from components.knowledge_card import knowledge_card

st.set_page_config(page_title="チャット", page_icon="💬", layout="wide")
st.title("💬 チャット（AI−勘ちゃん）")
st.caption("日々の疑問を記録する。AIは伴走者。最終判断は人間が行う。")

st.info(
    "現在はローカル記録モード（Phase1）です。\n"
    "質問と気づきを書いて保存しておきましょう。\n"
    "Phase3でベクトル検索・AI回答が繋がります。",
    icon="🌱",
)

# ── 入力 ──────────────────────────────────────────────────
with st.form("chat_form"):
    question = st.text_area("疑問・問い", placeholder="例：なぜトマトの葉が黄色くなるの？")
    answer = st.text_area(
        "気づき・調べたこと（自由記入）",
        placeholder="例：カリウム不足かも。基本書p.42を確認する。",
    )
    related_topics = st.text_input("関連トピック", placeholder="例：病害虫、土壌、トマト")
    source_type = st.selectbox(
        "知識の種別",
        ["souhatsuchi", "kenjinchi", "kasanatta"],
        format_func=lambda x: {"souhatsuchi": "🌸 創発知", "kenjinchi": "💙 賢人知",
                               "kasanatta": "💜 重なった知"}[x],
    )
    submitted = st.form_submit_button("記録する")
    if submitted and question:
        conn = get_connection()
        conn.execute(
            """INSERT INTO chat_logs (question, answer, related_topics, source_type)
               VALUES (?,?,?,?)""",
            (question, answer, related_topics, source_type),
        )
        conn.commit()
        conn.close()
        st.success("記録しました。")
        st.rerun()

# ── 記録一覧 ───────────────────────────────────────────────
st.markdown("---")
st.subheader("対話の記録")

conn = get_connection()
rows = conn.execute("SELECT * FROM chat_logs ORDER BY id DESC").fetchall()
conn.close()

if not rows:
    st.info("まだ対話記録がありません。")
else:
    search = st.text_input("🔍 絞り込み")
    for row in rows:
        r = dict(row)
        if search and search not in str(r.values()):
            continue
        title = r["question"][:60] + ("…" if len(r["question"]) > 60 else "")
        parts = []
        if r.get("answer"):
            parts.append(f"【気づき】{r['answer']}")
        if r.get("related_topics"):
            parts.append(f"【関連】{r['related_topics']}")
        parts.append(f"記録日時：{r.get('created_at', '')}")
        knowledge_card(title, "\n".join(parts), r.get("source_type", "souhatsuchi"))
