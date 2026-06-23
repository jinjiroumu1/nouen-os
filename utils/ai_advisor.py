import streamlit as st
from anthropic import Anthropic
from notion_client import Client

KENJIN_PAGE_ID  = "388a73ede4938018af0ddf46812b076d"
DIARY_DB_ID     = "09ad62605aa543cfac7139c50b1e9b4c"
MAX_TURNS = 3


def _notion():
    token = st.secrets.get("NOTION_TOKEN", "")
    return Client(auth=token) if token else None


def _claude():
    key = st.secrets.get("ANTHROPIC_API_KEY", "")
    return Anthropic(api_key=key) if key else None


def _block_texts(notion, block_id, depth=0):
    if depth > 2:
        return []
    try:
        blocks = notion.blocks.children.list(block_id=block_id, page_size=50)
    except Exception:
        return []
    texts = []
    for b in blocks.get("results", []):
        bt = b.get("type", "")
        rich = b.get(bt, {}).get("rich_text", []) if bt else []
        text = "".join(r.get("plain_text", "") for r in rich).strip()
        if text:
            texts.append(text)
        if b.get("has_children"):
            texts += _block_texts(notion, b["id"], depth + 1)
    return texts


def _fetch_kenjin():
    notion = _notion()
    if not notion:
        return "（賢人コーナー未取得）"
    texts = _block_texts(notion, KENJIN_PAGE_ID)
    return "\n".join(texts[:60]) or "（賢人コーナーは空です）"


def _fetch_past_diaries(crop=""):
    notion = _notion()
    if not notion:
        return "（過去記録未取得）"
    try:
        params = {
            "database_id": DIARY_DB_ID,
            "page_size": 8,
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        }
        if crop:
            params["filter"] = {"property": "作物", "rich_text": {"contains": crop}}
        results = notion.databases.query(**params)
        entries = []
        for page in results.get("results", []):
            props = page.get("properties", {})

            def get_text(name):
                p = props.get(name, {})
                t = p.get("type", "")
                key = "rich_text" if t == "rich_text" else "title" if t == "title" else None
                if key:
                    return "".join(r.get("plain_text", "") for r in p.get(key, []))
                return ""

            title = get_text("タイトル")
            obs   = get_text("観察・気づき")
            hypo  = get_text("仮説")
            work  = get_text("作業内容")
            if obs or hypo:
                entries.append(f"【{title}】作業:{work} 観察:{obs} 仮説:{hypo}")
        return "\n".join(entries) or "（関連する過去記録なし）"
    except Exception as e:
        return f"（取得エラー: {e}）"


def get_ai_response(diary_entry: dict, chat_history: list) -> str:
    client = _claude()
    if not client:
        return (
            "⚠️ AI勘ちゃんを使うには `ANTHROPIC_API_KEY` の設定が必要です。\n"
            "Streamlit Cloud の Secrets に追加してください。"
        )

    kenjin = _fetch_kenjin()
    past   = _fetch_past_diaries(crop=diary_entry.get("crop", ""))

    system = f"""あなたは「AI勘ちゃん」——われまち農縁団の伴走者です。

【役割】
農業日誌を受け取り、以下の優先順位で知恵を提供します。
① 基本書「ぐうたら農法」（西村和雄著）の考え方・哲学
② 賢人コーナーの知識（下記参照）
③ われまち農縁団の過去の記録（下記参照）

【回答形式】必ず以下4つに分けて回答してください：
【創発知】現場の気づき・仮説へのコメント（現場を尊重する）
【賢人知】基本書・賢人コーナーからの引用や知恵
【響き合う仮説】創発知と賢人知が響き合って生まれた仮説
【次に試すこと】具体的な提案を1〜3つ

【大切にすること】
- 創発知と賢人知を混同しない
- 断言せず、仮説として提案する
- 押し付けない。急がない。対話を大切にする
- 最終判断は人間が行う
- 3回の対話を想定し、毎回少しずつ深める

【賢人コーナーの内容】
{kenjin[:2000]}

【われまち農縁団の過去の記録（{diary_entry.get('crop', '') or '全般'}関連）】
{past[:2000]}
"""

    diary_text = "\n".join([
        f"日付：{diary_entry.get('date', '')}",
        f"天候：{diary_entry.get('weather', '')}",
        f"作物：{diary_entry.get('crop', '')}",
        f"作業：{diary_entry.get('work_done', '')}",
        f"観察・気づき：{diary_entry.get('observation', '')}",
        f"疑問：{diary_entry.get('question', '')}",
        f"仮説：{diary_entry.get('hypothesis', '')}",
    ])

    # 最初のユーザーメッセージは常に日誌の内容
    messages = [{"role": "user", "content": f"今日の農業日誌です。\n\n{diary_text}"}]
    messages += chat_history

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        system=system,
        messages=messages,
    )
    return response.content[0].text
