import streamlit as st
from anthropic import Anthropic
from notion_client import Client

KENJIN_PAGE_ID       = "388a73ede4938018af0ddf46812b076d"
DIARY_DB_ID          = "09ad62605aa543cfac7139c50b1e9b4c"
CULTIVATION_DB_ID    = "4694b1ccdb5e415da4246adbcb6b3527"
RECIPE_DB_ID         = "7f6528a1c78a4e1cbe1fd11af1dadfc0"
CHAT_DB_ID           = "fdd51460926141c2b2ce0b36adf474c2"
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


def _fetch_db_records(db_id, keyword_prop=None, keyword="", limit=6):
    notion = _notion()
    if not notion:
        return "（記録未取得）"
    try:
        params = {
            "database_id": db_id,
            "page_size": limit,
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        }
        if keyword and keyword_prop:
            params["filter"] = {"property": keyword_prop, "rich_text": {"contains": keyword}}
        results = notion.databases.query(**params)
        entries = []
        for page in results.get("results", []):
            props = page.get("properties", {})
            parts = []
            for name, prop in props.items():
                t = prop.get("type", "")
                if t == "title":
                    val = "".join(r.get("plain_text", "") for r in prop.get("title", []))
                elif t == "rich_text":
                    val = "".join(r.get("plain_text", "") for r in prop.get("rich_text", []))
                elif t == "select":
                    val = (prop.get("select") or {}).get("name", "")
                else:
                    continue
                if val:
                    parts.append(f"{name}:{val}")
            if parts:
                entries.append(" / ".join(parts[:6]))
        return "\n".join(entries) or "（関連記録なし）"
    except Exception as e:
        return f"（取得エラー: {e}）"


def _base_system(kenjin, past, role_desc):
    return f"""あなたは「AI勘ちゃん」——われまち農縁団の伴走者です。

【役割】
{role_desc}

【参照優先順位】
① 基本書「ぐうたら農法」（西村和雄著）の考え方・哲学
② 賢人コーナーの知識（下記参照）
③ われまち農縁団の過去の記録（下記参照）

【回答形式】必ず以下4つに分けて回答してください：
【創発知】現場の気づき・問いへのコメント（現場を尊重する）
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

【われまち農縁団の過去の記録】
{past[:2000]}
"""


def _call_claude(system, first_message, chat_history):
    client = _claude()
    if not client:
        return (
            "⚠️ AI勘ちゃんを使うには `ANTHROPIC_API_KEY` の設定が必要です。\n"
            "Streamlit Cloud の Secrets に追加してください。"
        )
    messages = [{"role": "user", "content": first_message}] + chat_history
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        system=system,
        messages=messages,
    )
    return response.content[0].text


# ── 農業日誌 ──────────────────────────────────────────────
def get_ai_response(diary_entry: dict, chat_history: list) -> str:
    kenjin = _fetch_kenjin()
    past   = _fetch_db_records(DIARY_DB_ID, "作物", diary_entry.get("crop", ""))
    system = _base_system(kenjin, past,
        "農業日誌の記録を受け取り、現場の気づきと基本書・賢人の知恵を響き合わせてコメントします。")
    first = "\n".join([
        f"日付：{diary_entry.get('date','')}",
        f"天候：{diary_entry.get('weather','')}",
        f"作物：{diary_entry.get('crop','')}",
        f"作業：{diary_entry.get('work_done','')}",
        f"観察・気づき：{diary_entry.get('observation','')}",
        f"疑問：{diary_entry.get('question','')}",
        f"仮説：{diary_entry.get('hypothesis','')}",
    ])
    return _call_claude(system, f"今日の農業日誌です。\n\n{first}", chat_history)


# ── 栽培計画 ──────────────────────────────────────────────
def get_ai_response_cultivation(entry: dict, chat_history: list) -> str:
    kenjin = _fetch_kenjin()
    past   = _fetch_db_records(CULTIVATION_DB_ID, "作物", entry.get("crop", ""))
    system = _base_system(kenjin, past,
        "栽培計画の内容を受け取り、基本書・賢人の知恵と過去の農縁団記録をもとにアドバイスします。"
        "コンパニオンプランツ、季節の適否、必要資材などを考慮します。")
    first = "\n".join([
        f"月：{entry.get('month','')}",
        f"作物：{entry.get('crop','')}",
        f"播種：{entry.get('sowing_date','')}",
        f"定植：{entry.get('planting_date','')}",
        f"収穫：{entry.get('harvest_period','')}",
        f"コンパニオンプランツ：{entry.get('companion_plants','')}",
        f"必要資材：{entry.get('required_materials','')}",
    ])
    return _call_claude(system, f"栽培計画を立てました。\n\n{first}", chat_history)


# ── 料理 ─────────────────────────────────────────────────
def get_ai_response_recipe(entry: dict, chat_history: list) -> str:
    kenjin = _fetch_kenjin()
    past   = _fetch_db_records(RECIPE_DB_ID, "主な野菜", entry.get("vegetable", ""))
    system = _base_system(kenjin, past,
        "料理・レシピの記録を受け取り、旬・保存性・原価率・田心カフェへの展開を考慮してコメントします。"
        "畑と食卓をつなぐ視点を大切にします。")
    first = "\n".join([
        f"料理名：{entry.get('recipe_name','')}",
        f"主な野菜：{entry.get('vegetable','')}",
        f"材料：{entry.get('ingredients','')}",
        f"季節：{entry.get('season','')}",
        f"メモ：{entry.get('notes','')}",
    ])
    return _call_claude(system, f"料理を記録しました。\n\n{first}", chat_history)


# ── チャット ─────────────────────────────────────────────
def get_ai_response_chat(entry: dict, chat_history: list) -> str:
    kenjin = _fetch_kenjin()
    past_diary = _fetch_db_records(DIARY_DB_ID, limit=5)
    past_chat  = _fetch_db_records(CHAT_DB_ID, limit=5)
    past = f"【過去の日誌】\n{past_diary}\n\n【過去のチャット】\n{past_chat}"
    system = _base_system(kenjin, past,
        "農業・料理・土壌・発酵・病害虫など日々の疑問に答えます。"
        "基本書「ぐうたら農法」の哲学を軸に、賢人の知恵と農縁団の記録を組み合わせます。")
    first = "\n".join([
        f"疑問：{entry.get('question','')}",
        f"関連トピック：{entry.get('related_topics','')}",
    ])
    return _call_claude(system, f"質問があります。\n\n{first}", chat_history)
