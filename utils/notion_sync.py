import streamlit as st
from notion_client import Client
from datetime import datetime, timezone

DB_IDS = {
    "farm_diary":        "09ad62605aa543cfac7139c50b1e9b4c",
    "cultivation_plans": "4694b1ccdb5e415da4246adbcb6b3527",
    "recipes":           "7f6528a1c78a4e1cbe1fd11af1dadfc0",
    "chat_logs":         "fdd51460926141c2b2ce0b36adf474c2",
}

ACCOUNTING_PAGE_ID = "388a73ede493800ea5fdd751647cba5d"
POP_PAGE_ID        = "38ba73ede49380a5beb6e30548302f30"

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
