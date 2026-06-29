import streamlit as st
from notion_client import Client
from datetime import datetime, timezone

DB_IDS = {
    "farm_diary":        "09ad62605aa543cfac7139c50b1e9b4c",
    "cultivation_plans": "4694b1ccdb5e415da4246adbcb6b3527",
    "recipes":           "7f6528a1c78a4e1cbe1fd11af1dadfc0",
    "chat_logs":         "fdd51460926141c2b2ce0b36adf474c2",
}

ACCOUNTING_PAGE_ID           = "388a73ede493800ea5fdd751647cba5d"
ACCOUNTING_DECISIONS_PAGE_ID = "644a9f42d1d74165bc1a1b75ab954766"
POP_PAGE_ID                  = "38ba73ede49380a5beb6e30548302f30"
HYGIENE_PAGE_ID              = "38ba73ede49380bbb4befb5d70db6726"

SOURCE_TYPE_LABEL = {
    "souhatsuchi": "🌸創発知",
    "kenjinchi":   "💙賢人知",
    "kasanatta":   "💜重なった知",
    "suuchi":      "🩶数値データ",
}


def _get_client():
    token = st.secrets.get("NOTION_TOKEN", "")
    if not token:
        return None
    return Client(auth=token)


def _select(value):
    return {"select": {"name": value}} if value else {"select": None}


def _rich_text(value):
    return {"rich_text": [{"text": {"content": str(value)[:2000]}}]} if value else {"rich_text": []}


def _title(value):
    return {"title": [{"text": {"content": str(value)[:2000]}}]}


def _date(value):
    return {"date": {"start": str(value)}} if value else {"date": None}


def save_farm_diary(date, weather, crop, work_done, observation, question, hypothesis, source_type):
    client = _get_client()
    if not client:
        return
    label = SOURCE_TYPE_LABEL.get(source_type, source_type)
    title_text = f"{date} / {crop}" if crop else str(date)
    try:
        client.pages.create(
            parent={"database_id": DB_IDS["farm_diary"]},
            properties={
                "タイトル":     _title(title_text),
                "日付":         _date(date),
                "天候":         _select(weather),
                "作物":         _rich_text(crop),
                "作業内容":     _rich_text(work_done),
                "観察・気づき": _rich_text(observation),
                "疑問・問い":   _rich_text(question),
                "仮説":         _rich_text(hypothesis),
                "知識の種別":   _select(label),
            },
        )
    except Exception as e:
        st.warning(f"Notion同期エラー（農業日誌）: {e}")


def save_cultivation_plan(month, crop, sowing_date, planting_date, harvest_period,
                           companion_plants, required_materials, source_type):
    client = _get_client()
    if not client:
        return
    label = SOURCE_TYPE_LABEL.get(source_type, source_type)
    try:
        client.pages.create(
            parent={"database_id": DB_IDS["cultivation_plans"]},
            properties={
                "タイトル":           _title(f"{month} / {crop}"),
                "月":                _select(month),
                "作物":              _rich_text(crop),
                "播種時期":           _rich_text(sowing_date),
                "定植時期":           _rich_text(planting_date),
                "収穫時期":           _rich_text(harvest_period),
                "コンパニオンプランツ": _rich_text(companion_plants),
                "必要資材":           _rich_text(required_materials),
                "知識の種別":         _select(label),
            },
        )
    except Exception as e:
        st.warning(f"Notion同期エラー（栽培計画）: {e}")


def save_recipe(recipe_name, vegetable, ingredients, season, notes, source_type):
    client = _get_client()
    if not client:
        return
    label = SOURCE_TYPE_LABEL.get(source_type, source_type)
    try:
        client.pages.create(
            parent={"database_id": DB_IDS["recipes"]},
            properties={
                "料理名":                _title(recipe_name),
                "主な野菜":              _rich_text(vegetable),
                "材料・分量":            _rich_text(ingredients),
                "季節":                 _select(season),
                "メモ（保存法・原価・人気）": _rich_text(notes),
                "知識の種別":            _select(label),
            },
        )
    except Exception as e:
        st.warning(f"Notion同期エラー（料理）: {e}")


def _get_or_create_db(client, page_id: str, db_title: str) -> str | None:
    """ページの子DBを検索し、なければ作成してIDを返す。"""
    try:
        results = client.blocks.children.list(block_id=page_id)
        for block in results.get("results", []):
            if block.get("type") == "child_database":
                title = block.get("child_database", {}).get("title", "")
                if title == db_title:
                    return block["id"].replace("-", "")
        # DBが存在しないので作成
        db = client.databases.create(
            parent={"page_id": page_id},
            title=[{"text": {"content": db_title}}],
            properties={
                "質問": {"title": {}},
                "回答": {"rich_text": {}},
                "日時": {"date": {}},
            },
        )
        return db["id"].replace("-", "")
    except Exception as e:
        st.warning(f"Notion DB取得/作成エラー: {e}")
        return None


def save_accounting_log(question: str, answer: str):
    """会計ページの子DBに質問・回答を保存する。"""
    client = _get_client()
    if not client:
        return
    db_id = _get_or_create_db(client, ACCOUNTING_PAGE_ID, "会計チャットログ")
    if not db_id:
        return
    try:
        now = datetime.now(timezone.utc).isoformat()
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "質問": _title(question),
                "回答": _rich_text(answer),
                "日時": _date(now),
            },
        )
    except Exception as e:
        st.warning(f"Notion同期エラー（会計）: {e}")


# titleプロパティはNotionが「名前」として自動生成するため除外
# 「品物名」は既存titleプロパティ（「名前」）を流用する
_DECISIONS_PROPS_EXTRA = {
    "カテゴリ": {"select": {}},
    "量":       {"rich_text": {}},
    "金額":     {"rich_text": {}},
    "備考":     {"rich_text": {}},
    "日時":     {"date": {}},
}


DECISIONS_DB_ID = "38ea73ede4938132956fcdbed01c0f5f"


def save_accounting_decision(item_name: str, category: str, quantity: str, price: str, note: str) -> bool:
    """会計決め事をDBに保存する。成功時True。"""
    client = _get_client()
    if not client:
        return False
    try:
        now = datetime.now(timezone.utc).isoformat()
        client.pages.create(
            parent={"database_id": DECISIONS_DB_ID},
            properties={
                "品物名":   _title(item_name),
                "カテゴリ": _select(category),
                "量":       _rich_text(quantity),
                "金額":     _rich_text(price),
                "備考":     _rich_text(note),
                "日時":     _date(now),
            },
        )
        return True
    except Exception as e:
        st.warning(f"Notion同期エラー（会計決め事）: {e}")
        return False


def load_accounting_decisions() -> list[dict]:
    """会計決め事を全件取得して返す。"""
    client = _get_client()
    if not client:
        return []
    try:
        items = []
        cursor = None
        while True:
            params = {
                "database_id": DECISIONS_DB_ID,
                "page_size": 100,
                "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            }
            if cursor:
                params["start_cursor"] = cursor
            res = client.databases.query(**params)
            for page in res.get("results", []):
                props = page.get("properties", {})
                name_val  = props.get("品物名", {}).get("title", [])
                cat_val   = props.get("カテゴリ", {})
                qty_val   = props.get("量", {}).get("rich_text", [])
                price_val = props.get("金額", {}).get("rich_text", [])
                note_val  = props.get("備考", {}).get("rich_text", [])
                item_name    = "".join(r.get("plain_text", "") for r in name_val)
                category     = (cat_val.get("select") or {}).get("name", "")
                quantity     = "".join(r.get("plain_text", "") for r in qty_val)
                price_text   = "".join(r.get("plain_text", "") for r in price_val)
                note_text    = "".join(r.get("plain_text", "") for r in note_val)
                if item_name or price_text:
                    items.append({
                        "item_name": item_name,
                        "category":  category,
                        "quantity":  quantity,
                        "price":     price_text,
                        "note":      note_text,
                    })
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        return items
    except Exception as e:
        st.warning(f"Notion取得エラー（会計決め事）: {e}")
        return []


def _get_or_create_purchase_db(client) -> str | None:
    """会計ページに仕入れ記録DBを取得または作成してIDを返す。"""
    try:
        results = client.blocks.children.list(block_id=ACCOUNTING_PAGE_ID)
        for block in results.get("results", []):
            if block.get("type") == "child_database":
                if block.get("child_database", {}).get("title", "") == "仕入れ記録":
                    return block["id"].replace("-", "")
        db = client.databases.create(
            parent={"page_id": ACCOUNTING_PAGE_ID},
            title=[{"text": {"content": "仕入れ記録"}}],
            properties={
                "商品名":       {"title": {}},
                "仕入日":       {"date": {}},
                "取引先":       {"rich_text": {}},
                "商品単価":     {"number": {"format": "yen"}},
                "仕入個数":     {"number": {"format": "number"}},
                "送料":         {"number": {"format": "yen"}},
                "消費税区分":   {"select": {}},
                "商品単価合計": {"number": {"format": "yen"}},
                "備考":         {"rich_text": {}},
            },
        )
        return db["id"].replace("-", "")
    except Exception as e:
        st.warning(f"Notion DB取得/作成エラー（仕入れ記録）: {e}")
        return None


def save_purchase_record(
    purchase_date: str,
    supplier: str,
    product_name: str,
    unit_price: float,
    quantity: int,
    shipping: float,
    tax_type: str,
    total_unit_price: float,
    note: str,
) -> bool:
    """仕入れ記録DBに1商品分を保存する。成功時True。"""
    client = _get_client()
    if not client:
        return False, "Notionクライアント初期化失敗"
    db_id = "38ea73ede49381aaa109e3909bdead98"
    try:
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "商品名":       _title(product_name),
                "仕入日":       _date(purchase_date),
                "取引先":       _rich_text(supplier),
                "商品単価":     {"number": unit_price},
                "仕入個数":     {"number": quantity},
                "送料":         {"number": shipping},
                "消費税区分":   _select(tax_type),
                "商品単価合計": {"number": total_unit_price},
                "備考":         _rich_text(note),
            },
        )
        return True, ""
    except Exception as e:
        return False, str(e)


def load_purchase_records(limit: int = 20) -> list[dict]:
    """仕入れ記録DBから直近のレコードを取得して返す。"""
    client = _get_client()
    if not client:
        return []
    db_id = "38ea73ede49381aaa109e3909bdead98"
    try:
        res = client.databases.query(**{
            "database_id": db_id,
            "page_size": limit,
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        })
        items = []
        for page in res.get("results", []):
            props = page.get("properties", {})
            def _txt(key):
                p = props.get(key, {})
                return "".join(r.get("plain_text", "") for r in p.get("rich_text", []))
            def _title(key):
                p = props.get(key, {})
                return "".join(r.get("plain_text", "") for r in p.get("title", []))
            def _num(key):
                return props.get(key, {}).get("number") or 0
            def _date(key):
                d = props.get(key, {}).get("date") or {}
                return d.get("start", "")
            items.append({
                "purchase_date":    _date("仕入日"),
                "supplier":         _txt("取引先"),
                "product_name":     _title("商品名"),
                "total_unit_price": _num("商品単価合計"),
                "quantity":         _num("仕入個数"),
            })
        return items
    except Exception as e:
        st.warning(f"Notion取得エラー（仕入れ記録）: {e}")
        return []


def save_pop_log(question: str, answer: str):
    """POPページの子DBに質問・回答を保存する。"""
    client = _get_client()
    if not client:
        return
    db_id = _get_or_create_db(client, POP_PAGE_ID, "POPチャットログ")
    if not db_id:
        return
    try:
        now = datetime.now(timezone.utc).isoformat()
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "質問": _title(question),
                "回答": _rich_text(answer),
                "日時": _date(now),
            },
        )
    except Exception as e:
        st.warning(f"Notion同期エラー（POP）: {e}")


def _get_or_create_expiry_db(client) -> str | None:
    """衛生ページに賞味期限管理DBを取得または作成してIDを返す。"""
    try:
        results = client.blocks.children.list(block_id=HYGIENE_PAGE_ID)
        for block in results.get("results", []):
            if block.get("type") == "child_database":
                title = block.get("child_database", {}).get("title", "")
                if title == "賞味期限管理":
                    return block["id"].replace("-", "")
        db = client.databases.create(
            parent={"page_id": HYGIENE_PAGE_ID},
            title=[{"text": {"content": "賞味期限管理"}}],
            properties={
                "商品名":   {"title": {}},
                "賞味期限": {"date": {}},
                "数量":     {"rich_text": {}},
                "保管場所": {"rich_text": {}},
                "備考":     {"rich_text": {}},
            },
        )
        return db["id"].replace("-", "")
    except Exception as e:
        st.warning(f"Notion DB取得/作成エラー（賞味期限）: {e}")
        return None


def save_expiry_item(product_name: str, expiry_date: str, quantity: str,
                     storage_location: str, note: str):
    """賞味期限管理DBに商品を保存する。"""
    client = _get_client()
    if not client:
        return False
    db_id = _get_or_create_expiry_db(client)
    if not db_id:
        return False
    try:
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "商品名":   _title(product_name),
                "賞味期限": _date(expiry_date),
                "数量":     _rich_text(quantity),
                "保管場所": _rich_text(storage_location),
                "備考":     _rich_text(note),
            },
        )
        return True
    except Exception as e:
        st.warning(f"Notion同期エラー（賞味期限）: {e}")
        return False


def load_expiry_items() -> list[dict]:
    """
    賞味期限管理DBの全レコードを取得して返す。
    返り値: [{"id": str, "product_name": str, "expiry_date": str,
               "quantity": str, "storage_location": str, "note": str}, ...]
    """
    client = _get_client()
    if not client:
        return []
    db_id = _get_or_create_expiry_db(client)
    if not db_id:
        return []
    try:
        results = client.databases.query(**{"database_id": db_id})
        items = []
        for page in results.get("results", []):
            props = page.get("properties", {})

            def _get_title(p):
                v = props.get(p, {}).get("title", [])
                return v[0]["text"]["content"] if v else ""

            def _get_text(p):
                v = props.get(p, {}).get("rich_text", [])
                return v[0]["text"]["content"] if v else ""

            def _get_date(p):
                v = props.get(p, {}).get("date")
                return v["start"] if v else ""

            items.append({
                "id":               page["id"],
                "product_name":     _get_title("商品名"),
                "expiry_date":      _get_date("賞味期限"),
                "quantity":         _get_text("数量"),
                "storage_location": _get_text("保管場所"),
                "note":             _get_text("備考"),
            })
        return items
    except Exception as e:
        st.warning(f"Notion読み込みエラー（賞味期限）: {e}")
        return []


def delete_expiry_item(page_id: str):
    """賞味期限管理DBのレコードをアーカイブ（削除）する。"""
    client = _get_client()
    if not client:
        return
    try:
        client.pages.update(page_id=page_id, archived=True)
    except Exception as e:
        st.warning(f"Notion削除エラー: {e}")


def load_chat_logs(limit: int = 30) -> list[dict]:
    """チャット記録DBから直近のログを取得して返す。"""
    client = _get_client()
    if not client:
        return []
    try:
        res = client.databases.query(**{
            "database_id": DB_IDS["chat_logs"],
            "page_size": limit,
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        })
        items = []
        for page in res.get("results", []):
            props = page.get("properties", {})
            q_val = props.get("疑問・問い", {}).get("title", [])
            a_val = props.get("気づき・回答", {}).get("rich_text", [])
            t_val = props.get("関連トピック", {}).get("rich_text", [])
            s_val = props.get("知識の種別", {})
            question    = "".join(r.get("plain_text", "") for r in q_val)
            answer      = "".join(r.get("plain_text", "") for r in a_val)
            topics      = "".join(r.get("plain_text", "") for r in t_val)
            source_type = (s_val.get("select") or {}).get("name", "")
            if question:
                items.append({
                    "question":      question,
                    "answer":        answer,
                    "related_topics": topics,
                    "source_type":   source_type,
                })
        return items
    except Exception as e:
        st.warning(f"Notion取得エラー（チャットログ）: {e}")
        return []


def save_chat_log(question, answer, related_topics, source_type):
    client = _get_client()
    if not client:
        return
    label = SOURCE_TYPE_LABEL.get(source_type, source_type)
    try:
        client.pages.create(
            parent={"database_id": DB_IDS["chat_logs"]},
            properties={
                "疑問・問い":   _title(question),
                "気づき・回答": _rich_text(answer),
                "関連トピック": _rich_text(related_topics),
                "知識の種別":   _select(label),
            },
        )
    except Exception as e:
        st.warning(f"Notion同期エラー（チャット）: {e}")
