import streamlit as st
from anthropic import Anthropic
from notion_client import Client

# ── ページID ──────────────────────────────────────────────
KENJIN_PAGE_ID       = "388a73ede4938018af0ddf46812b076d"
DIARY_PAGE_ID        = "388a73ede49380959b76eccab430ad1c"
CULTIVATION_PAGE_ID  = "388a73ede4938078afd6cce318d5b741"
RECIPE_PAGE_ID       = "388a73ede4938076b4abd0b27c921982"
CHAT_PAGE_ID         = "388a73ede493806bb1d5d66ad8ddad07"

# ── データベースID ────────────────────────────────────────
DIARY_DB_ID          = "09ad62605aa543cfac7139c50b1e9b4c"
CULTIVATION_DB_ID    = "4694b1ccdb5e415da4246adbcb6b3527"
RECIPE_DB_ID         = "7f6528a1c78a4e1cbe1fd11af1dadfc0"
CHAT_DB_ID           = "fdd51460926141c2b2ce0b36adf474c2"

MAX_TURNS = 3
_TEXT_LIMIT = 3000   # 1ページあたりの最大文字数


def _notion():
    token = st.secrets.get("NOTION_TOKEN", "")
    return Client(auth=token) if token else None


def _claude():
    key = st.secrets.get("ANTHROPIC_API_KEY", "")
    return Anthropic(api_key=key) if key else None


# ── ページ本文テキストを取得（ブロック再帰） ──────────────
def _block_texts(notion, block_id, depth=0):
    """ページ内のテキストブロックを再帰的に取得（depth上限3）"""
    if depth > 3:
        return []
    try:
        blocks = notion.blocks.children.list(block_id=block_id, page_size=100)
    except Exception:
        return []
    texts = []
    for b in blocks.get("results", []):
        bt = b.get("type", "")
        # テキスト系ブロック
        if bt in ("paragraph", "heading_1", "heading_2", "heading_3",
                  "bulleted_list_item", "numbered_list_item", "quote", "callout"):
            rich = b.get(bt, {}).get("rich_text", [])
            text = "".join(r.get("plain_text", "") for r in rich).strip()
            if text:
                texts.append(text)
        # 子ブロックがあれば再帰
        if b.get("has_children") and bt != "child_database":
            texts += _block_texts(notion, b["id"], depth + 1)
    return texts


# ── ページ＋子ページを全部読む ────────────────────────────
@st.cache_data(ttl=300)   # 5分キャッシュ（子ページが増えても再取得される）
def fetch_page_tree(page_id: str, label: str = "") -> str:
    """
    指定ページ本文 + すべての子ページ本文を結合して返す。
    データベース（child_database）は別途DBクエリで取得するのでスキップ。
    """
    notion = _notion()
    if not notion:
        return ""

    all_texts = []

    def _crawl(pid, title=""):
        try:
            blocks = notion.blocks.children.list(block_id=pid, page_size=100)
        except Exception:
            return
        page_texts = []
        child_pages = []

        for b in blocks.get("results", []):
            bt = b.get("type", "")
            if bt == "child_page":
                child_title = b.get("child_page", {}).get("title", "")
                child_pages.append((b["id"], child_title))
            elif bt == "child_database":
                pass   # DBはDBクエリで取得
            elif bt in ("paragraph", "heading_1", "heading_2", "heading_3",
                        "bulleted_list_item", "numbered_list_item", "quote", "callout"):
                rich = b.get(bt, {}).get("rich_text", [])
                text = "".join(r.get("plain_text", "") for r in rich).strip()
                if text:
                    page_texts.append(text)
            if b.get("has_children") and bt not in ("child_page", "child_database"):
                page_texts += _block_texts(notion, b["id"], depth=1)

        if page_texts:
            header = f"\n### {title}\n" if title else ""
            all_texts.append(header + "\n".join(page_texts))

        for cid, ctitle in child_pages:
            _crawl(cid, ctitle)

    _crawl(page_id, label)
    result = "\n".join(all_texts)
    return result[:_TEXT_LIMIT] if result else "（内容なし）"


# ── DBレコードを取得 ──────────────────────────────────────
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


# ── システムプロンプト共通 ────────────────────────────────
def _base_system(kenjin, past, role_desc):
    return f"""あなたは「AI勘ちゃん」——われまち農縁団の伴走者です。

【役割】
{role_desc}

【参照優先順位】
① 基本書「ぐうたら農法」（西村和雄著）の考え方・哲学
② 賢人コーナーの知識（下記参照）
③ われまち農縁団の過去の記録・子ページ（下記参照）

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

【賢人コーナー（本文＋子ページすべて）】
{kenjin}

【われまち農縁団の記録（本文＋子ページ＋DB）】
{past}
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
    kenjin = fetch_page_tree(KENJIN_PAGE_ID, "賢人コーナー")
    past_page = fetch_page_tree(DIARY_PAGE_ID, "日誌ページ")
    past_db   = _fetch_db_records(DIARY_DB_ID, "作物", diary_entry.get("crop", ""))
    past = f"{past_page}\n\n【農業日誌DB】\n{past_db}"
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
    kenjin = fetch_page_tree(KENJIN_PAGE_ID, "賢人コーナー")
    past_page = fetch_page_tree(CULTIVATION_PAGE_ID, "栽培計画ページ")
    past_db   = _fetch_db_records(CULTIVATION_DB_ID, "作物", entry.get("crop", ""))
    past = f"{past_page}\n\n【栽培計画DB】\n{past_db}"
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
    kenjin = fetch_page_tree(KENJIN_PAGE_ID, "賢人コーナー")
    past_page = fetch_page_tree(RECIPE_PAGE_ID, "料理ページ")
    past_db   = _fetch_db_records(RECIPE_DB_ID, "主な野菜", entry.get("vegetable", ""))
    past = f"{past_page}\n\n【料理レシピDB】\n{past_db}"
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
    kenjin = fetch_page_tree(KENJIN_PAGE_ID, "賢人コーナー")
    past_diary = fetch_page_tree(DIARY_PAGE_ID, "日誌ページ")
    past_chat  = fetch_page_tree(CHAT_PAGE_ID, "チャットコーナー")
    past_db    = _fetch_db_records(DIARY_DB_ID, limit=5)
    past = f"{past_diary}\n\n{past_chat}\n\n【日誌DB】\n{past_db}"
    system = _base_system(kenjin, past,
        "農業・料理・土壌・発酵・病害虫など日々の疑問に答えます。"
        "基本書「ぐうたら農法」の哲学を軸に、賢人の知恵と農縁団の記録を組み合わせます。")
    first = "\n".join([
        f"疑問：{entry.get('question','')}",
        f"関連トピック：{entry.get('related_topics','')}",
    ])
    return _call_claude(system, f"質問があります。\n\n{first}", chat_history)
