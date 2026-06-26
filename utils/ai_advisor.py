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

SOURCE_TYPE_LABEL = {
    "souhatsuchi": "🌸創発知",
    "kenjinchi":   "💙賢人知",
    "kasanatta":   "💜重なった知",
    "suuchi":      "🩶数値データ",
}


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
        query_params = {
            "database_id": db_id,
            "page_size": limit,
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        }
        if keyword and keyword_prop:
            query_params["filter"] = {"property": keyword_prop, "rich_text": {"contains": keyword}}
        results = notion.databases.query(**query_params)
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
    from utils.book_loader import load_books
    pdf_files = load_books()
    if pdf_files:
        book_list = "\n".join(f"  - 『{b['name'].replace('.pdf','')}』" for b in pdf_files)
        book_note = f"① 添付された基本書・参考書PDF（各資料を区別して参照）\n{book_list}"
        pdf_section = """
【参照資料について】
- 各資料はファイル名で区別してください
- 回答時は必ず「資料名『○○』によれば」と明記してください
- 異なる資料の内容を混同しないでください
"""
    else:
        book_note = "① 基本書「ぐうたら農法」（西村和雄著）の考え方・哲学"
        pdf_section = ""

    return f"""あなたは「AI勘ちゃん」——われまち農縁団の伴走者です。

【役割】
{role_desc}

【参照優先順位】
{book_note}
② 賢人コーナーの知識（下記参照）
③ われまち農縁団の過去の記録・子ページ（下記参照）
{pdf_section}
【回答形式】必ず以下4つに分けて回答してください：
【創発知】現場の気づき・問いへのコメント（現場を尊重する）
【賢人知】基本書・賢人コーナーからの引用や知恵（資料名を明記）
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


def _call_claude(system, first_message, chat_history, use_books=True, extra_pdfs=None):
    client = _claude()
    if not client:
        return (
            "⚠️ AI勘ちゃんを使うには `ANTHROPIC_API_KEY` の設定が必要です。\n"
            "Streamlit Cloud の Secrets に追加してください。"
        )

    # PDF/Wordブロックを取得（use_books=False の場合はスキップ）
    pdf_blocks = []
    if use_books:
        from utils.book_loader import load_books
        books = load_books()
        word_texts = []
        for b in books:
            if b.get("type") == "word":
                word_texts.append(f"【{b['name']}】\n{b['text'][:3000]}")
            else:
                pdf_blocks.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b["data"],
                    },
                    "title": b["name"],
                })
        if word_texts:
            system = system + "\n\n【基本書（Word）】\n" + "\n\n".join(word_texts)

    # 追加PDF（請求書など）
    if extra_pdfs:
        for b in extra_pdfs:
            pdf_blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b["data"],
                },
                "title": b["name"],
            })

    # スプレッドシートデータをシステムプロンプトに追加
    from utils.sheets_loader import load_sheets
    sheets_text = load_sheets()
    if sheets_text:
        system = system + f"\n\n【販売・原価データ（スプレッドシート）】\n{sheets_text[:3000]}"

    # 最初のメッセージにPDFブロックを付加
    if pdf_blocks:
        first_content = pdf_blocks + [{"type": "text", "text": first_message}]
    else:
        first_content = first_message

    messages = [{"role": "user", "content": first_content}] + chat_history
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


# ── 会計・原価管理 ─────────────────────────────────────────
def get_ai_response_accounting(question: str, chat_history: list) -> str:
    """会計・原価・販売データ・請求書PDFを参照してAI勘ちゃんが回答する。"""
    from utils.sheets_loader import load_sheets
    sheets_text = load_sheets()

    system = f"""あなたは「AI勘ちゃん」——われまち農縁団の会計・原価管理アドバイザーです。

【役割】
原価計算・販売データ・支払い状況を具体的な数値とともに分析し、
農縁団の経営改善に役立つアドバイスをします。

【参照データ】
{sheets_text[:4000] if sheets_text else "（スプレッドシートが未設定です）"}

【回答のルール】
- 数値データを具体的に引用して回答する
- 原価率・利益率など計算が必要な場合は計算過程も示す
- データがない場合は「データが見つかりません」と正直に伝える
- 改善提案は具体的・実践的に
"""
    return _call_claude(system, question, chat_history, use_books=False)


def extract_delivery_note(image_bytes: bytes, media_type: str) -> dict:
    """
    納品書画像をClaude APIに送り、複数商品対応で情報を抽出する。
    返り値: {
      "date": str,
      "farmer_name": str,
      "shipping_fee": float,
      "items": [{"product_name": str, "purchase_price": float,
                 "total_weight": float, "unit_weight": float}, ...],
      "error": str  # エラー時のみ
    }
    """
    import base64, json, re
    client = _claude()
    if not client:
        return {"error": "ANTHROPIC_API_KEY が未設定です"}

    b64 = base64.standard_b64encode(image_bytes).decode()
    prompt = """この納品書画像から情報を抽出し、以下のJSON形式で返してください。
複数商品がある場合は items 配列に全て列挙してください。
不明な項目は null、数値は単位なしの数字のみで返してください。

{
  "date": "日付（YYYY-MM-DD、不明ならそのまま）",
  "farmer_name": "農家さん・仕入先名",
  "shipping_fee": 送料合計（数値）,
  "items": [
    {
      "product_name": "商品名",
      "purchase_price": 仕入価格（数値）,
      "total_weight": 全体の重さg（数値）,
      "unit_weight": 1商品の重さg（数値）
    }
  ]
}

JSONのみ返してください。"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = response.content[0].text
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            return json.loads(m.group())
        return {"error": f"JSON解析失敗: {text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


# ── ネットワーク図：自由チャット ──────────────────────────
def get_ai_response_network(question: str, chat_history: list) -> str:
    """ネットワーク図用の自由チャット。回答後にノード抽出を行う。"""
    kenjin    = fetch_page_tree(KENJIN_PAGE_ID, "賢人コーナー")
    past_diary = _fetch_db_records(DIARY_DB_ID, limit=5)
    past_chat  = _fetch_db_records(CHAT_DB_ID, limit=5)
    past = f"【日誌DB】\n{past_diary}\n\n【チャットDB】\n{past_chat}"

    system = f"""あなたは「AI勘ちゃん」——われまち農縁団の伴走者です。

質問に対して、基本書「ぐうたら農法」・賢人コーナー・農縁団の記録を参照して答えてください。
回答は簡潔に、わかりやすく。

【賢人コーナー】
{kenjin[:1500]}

【農縁団の記録】
{past[:1500]}
"""
    messages = [{"role": "user", "content": question}] + chat_history
    client = _claude()
    if not client:
        return "⚠️ ANTHROPIC_API_KEY が必要です。"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        system=system,
        messages=messages,
    )
    return response.content[0].text


# ── ネットワーク図：ノード・エッジ抽出 ───────────────────
def extract_nodes_and_edges(question: str, answer: str) -> dict:
    """
    会話（question + answer）から概念を抽出し、
    ノード候補・エッジ候補をJSONで返す。
    """
    import json
    client = _claude()
    if not client:
        return {"nodes": [], "edges": []}

    prompt = f"""以下の会話からノードとエッジを抽出してください。

【会話】
Q: {question}
A: {answer}

【ルール】
- 会話に実際に登場した概念だけをノード化する
- 書籍・PDF全体をノード化しない
- 色分け：
  - souhatsuchi（pink）：現場・実感・仲間の発言から出た概念
  - kenjinchi（blue）：賢人知・基本書・専門知識から出た概念
  - kasanatta（purple）：両方が重なった概念
  - suuchi（gray）：数値・会計・収穫量など

以下のJSON形式のみで返してください（説明文は不要）：
{{
  "nodes": [
    {{"label": "概念名", "source_type": "souhatsuchi|kenjinchi|kasanatta|suuchi"}}
  ],
  "edges": [
    {{"from_node": "概念A", "to_node": "概念B", "relationship": "関係の説明"}}
  ]
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {"nodes": [], "edges": []}


# ── ネットワーク図：ノード解説（過去の会話を検索） ────────
def get_node_explanation(node_label: str) -> str:
    """指定したノードに関する過去の会話・記録を検索して解説する。"""
    notion = _notion()
    client = _claude()
    if not client:
        return "⚠️ ANTHROPIC_API_KEY が必要です。"

    # Notionの各DBから関連記録を検索
    related = []
    for db_id, name in [
        (DIARY_DB_ID, "農業日誌"),
        (CHAT_DB_ID, "チャット"),
        (RECIPE_DB_ID, "料理"),
        (CULTIVATION_DB_ID, "栽培計画"),
    ]:
        records = _fetch_db_records(db_id, limit=20)
        # node_labelを含む記録だけ絞り込む
        lines = [line for line in records.split("\n") if node_label in line]
        if lines:
            related.append(f"【{name}】\n" + "\n".join(lines[:5]))

    context = "\n\n".join(related) if related else "（関連する記録が見つかりませんでした）"

    prompt = f"""われまち農縁団の記録の中で「{node_label}」に関してどんな会話・記録がありましたか？

【関連記録】
{context}

以下の形式で簡潔にまとめてください：
- 農縁団でどんな文脈で登場したか
- 関連する気づき・仮説があれば
- 今後深めると良いこと（あれば）"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── ネットワーク図：Notionデータ全体からノード・エッジ自動生成 ──
def build_network_from_notion() -> dict:
    """
    Notionのカンパニーブレイン構想内の全データを読み込み、
    AIがノードとエッジを抽出して返す。30分キャッシュ。
    """
    import json

    diary       = _fetch_db_records(DIARY_DB_ID, limit=30)
    cultivation = _fetch_db_records(CULTIVATION_DB_ID, limit=30)
    recipe      = _fetch_db_records(RECIPE_DB_ID, limit=30)
    chat        = _fetch_db_records(CHAT_DB_ID, limit=30)
    notion_pages = fetch_page_tree(DIARY_PAGE_ID, "農業日誌ページ")

    all_text = f"""【農業日誌】
{diary[:1500]}

【栽培計画】
{cultivation[:1000]}

【料理記録】
{recipe[:1500]}

【チャット・対話記録】
{chat[:1000]}

【Notionページ記録】
{notion_pages[:1000]}
"""

    client = _claude()
    if not client:
        return {"nodes": [], "edges": []}

    prompt = f"""われまち農縁団の記録から、概念のネットワーク図を作ってください。

【記録】
{all_text}

【抽出ルール】
- 記録に実際に登場した語句・固有名詞・料理名・野菜名・作物名・行動をそのままノード化する
- 例：「なすのあげびたし」「なす」「夏」「冷たい料理」などは全てノード化する
- 抽象的な概念だけでなく、具体的な料理名・野菜名・人名・場所名も必ずノード化する
- 書籍・PDF全体はノード化しない
- 30〜50個程度抽出する
- 色分け：
  - souhatsuchi：現場・実感・農縁団の記録から出た具体的な語句（料理名・野菜名・出来事など）
  - kenjinchi：賢人知・専門知識・基本書から出た概念
  - kasanatta：両方が重なった概念
  - suuchi：数値・収穫量・原価・会計データ

以下のJSON形式のみで返してください（説明文不要）：
{{
  "nodes": [
    {{"label": "概念名", "source_type": "souhatsuchi|kenjinchi|kasanatta|suuchi"}}
  ],
  "edges": [
    {{"from_node": "概念A", "to_node": "概念B", "relationship": "関係の説明"}}
  ]
}}"""

    # PDFは渡さない（Notionデータのみでノード抽出）
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    # コードブロック（```json ... ```）を除去
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception as e:
        return {"nodes": [], "edges": [], "_debug": f"JSON解析エラー: {e}\n原文: {text[:300]}"}
