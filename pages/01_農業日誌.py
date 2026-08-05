import streamlit as st
import pandas as pd
from datetime import date
from db.database import get_connection
from utils.notion_sync import save_farm_diary, update_farm_diary_likes
from utils.ai_advisor import get_ai_response, MAX_TURNS

st.set_page_config(page_title="農業日誌", page_icon="🌿", layout="wide")
from pathlib import Path as _P
_img = _P("docs/characters/tsurezure.png")
if _img.exists():
    st.sidebar.image(str(_img), width=150)
st.title("🌿 農業日誌")
st.caption("共同体の記憶を記録する。天候・作業・気づきをここに。")

# ── セッション初期化 ───────────────────────────────────────
if "diary_entry" not in st.session_state:
    st.session_state.diary_entry = None   # 直近に保存した日誌
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []    # AIとのやり取り履歴
if "ai_responses" not in st.session_state:
    st.session_state.ai_responses = []    # 表示用（役割付き）
if "liked_pages" not in st.session_state:
    st.session_state.liked_pages = []    # セッション中にいいね済みのpage_id（list で保持）
if "likes_delta" not in st.session_state:
    st.session_state.likes_delta = {}    # page_id -> 加算済みいいね数（キャッシュ補正用）

# ── 入力フォーム ──────────────────────────────────────────
with st.expander("📝 新しい日誌を書く", expanded=True):
    with st.form("diary_form"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            entry_date = st.date_input("日付", value=date.today())
        with col2:
            weather = st.selectbox("天候", ["晴れ", "曇り", "雨", "雪", "その他"])
        with col3:
            crop = st.text_input("作物", placeholder="例：トマト、きゅうり")
        with col4:
            author = st.text_input("書いた人", placeholder="例：矢萩")

        work_done    = st.text_area("作業内容", placeholder="今日やったこと")
        observation  = st.text_area("観察・気づき（創発知）", placeholder="現場で感じたこと・変化")
        question     = st.text_input("疑問・問い", placeholder="なぜ？どうして？")
        hypothesis   = st.text_area("仮説", placeholder="こうじゃないかな…")

        source_type = st.selectbox(
            "知識の種別",
            ["souhatsuchi", "kenjinchi", "kasanatta", "suuchi"],
            format_func=lambda x: {
                "souhatsuchi": "🌸 創発知",
                "kenjinchi":   "💙 賢人知",
                "kasanatta":   "💜 重なった知",
                "suuchi":      "🩶 数値データ",
            }[x],
        )

        submitted = st.form_submit_button("記録する")
        if submitted:
            conn = get_connection()
            conn.execute(
                """INSERT INTO farm_diary
                   (date, weather, crop, work_done, observation, question, hypothesis, source_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (str(entry_date), weather, crop, work_done, observation,
                 question, hypothesis, source_type),
            )
            conn.commit()
            conn.close()
            save_farm_diary(entry_date, weather, crop, work_done, observation,
                            question, hypothesis, source_type, author)

            # AI対話のリセット＆日誌を保存
            st.session_state.diary_entry = {
                "date":        str(entry_date),
                "weather":     weather,
                "crop":        crop,
                "work_done":   work_done,
                "observation": observation,
                "question":    question,
                "hypothesis":  hypothesis,
            }
            st.session_state.chat_history  = []
            st.session_state.ai_responses  = []

            # 1回目のAI返答を自動取得
            with st.spinner("AI勘ちゃんが考えています…"):
                reply = get_ai_response(st.session_state.diary_entry, [])
            st.session_state.ai_responses.append({"role": "assistant", "content": reply})
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.success("記録しました。（Notionにも同期）")
            st.rerun()

# ── AI勘ちゃんとの対話 ────────────────────────────────────
if st.session_state.diary_entry:
    st.markdown("---")
    st.subheader("🤝 AI勘ちゃんからのコメント")
    st.caption(f"作物：{st.session_state.diary_entry.get('crop','—')}　｜　最大{MAX_TURNS}回の対話")

    # 対話履歴の表示
    for msg in st.session_state.ai_responses:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="🌱"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user", avatar="👨‍🌾"):
                st.markdown(msg["content"])

    # ユーザーが返信できる回数を計算
    user_turns = sum(1 for m in st.session_state.chat_history if m["role"] == "user")

    if user_turns < MAX_TURNS - 1:
        user_input = st.chat_input(
            f"勘ちゃんへの返事・追加の問い（あと{MAX_TURNS - 1 - user_turns}回）"
        )
        if user_input:
            st.session_state.ai_responses.append({"role": "user", "content": user_input})
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            with st.spinner("勘ちゃんが考えています…"):
                reply = get_ai_response(
                    st.session_state.diary_entry,
                    st.session_state.chat_history,
                )
            st.session_state.ai_responses.append({"role": "assistant", "content": reply})
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.rerun()
    else:
        st.info("今日の対話はここまで。記録お疲れさまでした。育てる。食べる。学ぶ。循環する。🌱")

    if st.button("対話をリセットして新しい日誌へ"):
        st.session_state.diary_entry   = None
        st.session_state.chat_history  = []
        st.session_state.ai_responses  = []
        st.rerun()

# ── 過去の日誌一覧（NotionDB から取得）────────────────────
st.markdown("---")
st.subheader("過去の日誌")

from utils.ai_advisor import _fetch_db_records, _notion, DIARY_DB_ID

@st.cache_data(ttl=60)
def _load_diary_from_notion():
    notion = _notion()
    if not notion:
        return []
    try:
        res = notion.databases.query(
            database_id=DIARY_DB_ID,
            page_size=50,
            sorts=[{"timestamp": "created_time", "direction": "descending"}],
        )
        rows = []
        for page in res.get("results", []):
            props = page.get("properties", {})
            def txt(key):
                p = props.get(key, {})
                t = p.get("type", "")
                if t == "title":
                    return "".join(r.get("plain_text","") for r in p.get("title",[]))
                if t == "rich_text":
                    return "".join(r.get("plain_text","") for r in p.get("rich_text",[]))
                if t == "select":
                    return (p.get("select") or {}).get("name","")
                return ""
            likes_prop = props.get("いいね数", {})
            likes = likes_prop.get("number") or 0
            rows.append({
                "page_id":     page["id"],
                "title":       txt("タイトル"),
                "crop":        txt("作物"),
                "work_done":   txt("作業内容"),
                "observation": txt("観察・気づき"),
                "hypothesis":  txt("仮説"),
                "question":    txt("疑問・問い"),
                "source_type": txt("知識の種別") or "souhatsuchi",
                "author":      txt("書いた人"),
                "likes":       int(likes),
            })
        return rows
    except Exception as e:
        st.warning(f"Notionから日誌を取得できませんでした: {e}")
        return []

notion_rows = _load_diary_from_notion()

# SQLiteにもあれば合わせて表示
conn = get_connection()
sqlite_rows = [dict(r) for r in conn.execute("SELECT * FROM farm_diary ORDER BY date DESC, id DESC").fetchall()]
conn.close()

all_rows = notion_rows if notion_rows else sqlite_rows

if not all_rows:
    st.info("まだ日誌がありません。上のフォームから記録を始めましょう。")
else:
    search = st.text_input("🔍 絞り込み（作物・作業・気づき）")
    SOURCE_ICON = {"souhatsuchi": "🌸", "kenjinchi": "💙", "kasanatta": "💜", "suuchi": "🩶"}
    for row in all_rows:
        if search and search not in str(row.values()):
            continue

        page_id       = row.get("page_id", "")
        likes         = row.get("likes", 0) + st.session_state.likes_delta.get(page_id, 0)
        already_liked = page_id in st.session_state.liked_pages
        title         = row.get("title") or f"{row.get('date','')} ／ {row.get('crop','—')}"
        src_icon      = SOURCE_ICON.get(row.get("source_type", "souhatsuchi"), "📝")

        with st.container(border=True):
            # 1行目：日付・いいね
            r1c1, r1c2 = st.columns([7, 1])
            r1c1.markdown(f"**{title}** {src_icon}")
            with r1c2:
                like_label = f"✅ {likes}" if already_liked else f"👍 {likes}"
                if page_id and not already_liked:
                    if st.button(like_label, key=f"like_{page_id}"):
                        ok, err = update_farm_diary_likes(page_id, likes)
                        if ok:
                            st.session_state.liked_pages.append(page_id)
                            st.session_state.likes_delta[page_id] = \
                                st.session_state.likes_delta.get(page_id, 0) + 1
                            st.rerun()
                        else:
                            st.error(f"いいね失敗: {err}")
                else:
                    st.caption(like_label)

            # 2行目：書いた人
            if row.get("author"):
                st.caption(f"✍️ {row['author']}")

            # 3行目以降：本文
            if row.get("work_done"):
                st.markdown(f"**作業** {row['work_done']}")
            if row.get("observation"):
                st.markdown(f"**観察・気づき** {row['observation']}")
            if row.get("question"):
                st.markdown(f"**疑問・問い** {row['question']}")
            if row.get("hypothesis"):
                st.markdown(f"**仮説** {row['hypothesis']}")
