"""
╔══════════════════════════════════════════════════════════╗
║  🇫🇷 FRANCE TRAVEL BOT — ВЕРСИЯ 5                        ║
║  Фильтр: цена/чел ≤ €70 · Без звёзд Michelin            ║
╠══════════════════════════════════════════════════════════╣
║  Новое в v5:                                             ║
║  • Фильтр по цене/чел (€50 / €60 / €70)                  ║
║  • Michelin-бейдж на каждом ресторане                    ║
║  • Звёздные рестораны автоматически исключаются          ║
║  • Порядок фильтров: кол-во отзывов → рейтинг → цена     ║
╚══════════════════════════════════════════════════════════╝
"""

import math, httpx, urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

TELEGRAM_TOKEN = "8408104861:AAFY7m6_Ztbo9_lZKZB5LV7PWEP2W4OBv6E"
ANTHROPIC_KEY  = "54bc281d-d281-4f12-8a2b-7b09558f3e48"

HOTEL = {"name": "Les Sources de Cheverny", "lat": 47.4972, "lon": 1.4583,
         "site": "lessourcesdecheverny.com"}

# ── MICHELIN СТАТУСЫ ──────────────────────────────────────────────────────────
# "star1" / "star2"  → ВСЕГДА исключаются из фильтра
# "bib"              → 🍽️ Bib Gourmand  (нет звезды, хорошая цена)
# "guide"            → 📖 В Guide Michelin (рекомендован, нет звезды)
# None               → нет упоминания в Michelin

def michelin_badge(status: str | None) -> str:
    return {"bib": " 🍽️ Bib Gourmand", "guide": " 📖 Guide Michelin",
            "star1": " ⭐ Michelin ★", "star2": " ⭐⭐ Michelin ★★"}.get(status or "", "")

# ── РЕСТОРАНЫ ─────────────────────────────────────────────────────────────────
# price_pp — ужин 3 блюда без напитков, €/чел
RESTAURANTS = {
    # ── Этрета · 11 июля ──────────────────────────────────────────────────────
    "r_casino": {
        "name": "Restaurant du Casino JOA", "city": "Etretat",
        "date": "20250711", "date_ru": "11 июля",
        "emoji": "🌊", "rating": 4.2, "reviews": 523,
        "price_pp": 50, "cuisine": "Французская · Морепродукты",
        "note": "Панорамный вид на море · Элегантная атмосфера",
        "michelin": None, "starred": False
    },
    "r_1635": {
        "name": "Le 1635", "city": "Etretat",
        "date": "20250711", "date_ru": "11 июля",
        "emoji": "🌊", "rating": 4.3, "reviews": 612,
        "price_pp": 45, "cuisine": "Нормандская французская",
        "note": "Аутентичная нормандская кухня · Уютная атмосфера",
        "michelin": None, "starred": False
    },
    # ── Трувиль · 12–13 июля ─────────────────────────────────────────────────
    "r2": {
        "name": "Les Mouettes", "city": "Trouville-sur-Mer",
        "date": "20250712", "date_ru": "12 июля",
        "emoji": "🏖️", "rating": 4.4, "reviews": 2568,
        "price_pp": 50, "cuisine": "Морепродукты · Нормандская",
        "note": "Рекорд по числу отзывов в Трувиле",
        "michelin": "guide", "starred": False
    },
    "r3": {
        "name": "Le Noroit", "city": "Trouville-sur-Mer",
        "date": "20250713", "date_ru": "13 июля",
        "emoji": "🏖️", "rating": 4.5, "reviews": 1188,
        "price_pp": 45, "cuisine": "Французская · Морепродукты",
        "note": "Любимец местных жителей",
        "michelin": None, "starred": False
    },
    "r4": {
        "name": "Les Docks", "city": "Trouville-sur-Mer",
        "date": "20250712", "date_ru": "12 июля (альт.)",
        "emoji": "🏖️", "rating": 4.5, "reviews": 1064,
        "price_pp": 45, "cuisine": "Морепродукты",
        "note": "Альтернатива Les Mouettes",
        "michelin": None, "starred": False
    },
    "r5": {
        "name": "Brasserie Les Bains", "city": "Trouville-sur-Mer",
        "date": "20250712", "date_ru": "12 июля (альт.)",
        "emoji": "🏖️", "rating": 4.3, "reviews": 1001,
        "price_pp": 45, "cuisine": "Французская брассери",
        "note": "Историческая элегантная брассери",
        "michelin": None, "starred": False
    },
    # ── Район замков · 14–17 июля (от Les Sources de Cheverny) ───────────────
    "r_auberge": {
        "name": "L'Auberge", "city": "Les Sources de Cheverny (в отеле)",
        "date": "20250714", "date_ru": "14 июля 🎆",
        "emoji": "🏨", "rating": 4.7, "reviews": 620,
        "price_pp": 50, "cuisine": "Биcтрономия · Дровая печь",
        "note": "⚡ ЛУЧШИЙ выбор 14 июля — в вашем отеле · 0 км · открыт на День Бастилии",
        "michelin": "bib", "starred": False
    },
    "r_pecheurs": {
        "name": "Au Rendez-vous des Pêcheurs", "city": "Blois (~20 км от отеля)",
        "date": "20250715", "date_ru": "15 июля",
        "emoji": "🐟", "rating": 4.5, "reviews": 830,
        "price_pp": 55, "cuisine": "Рыба Луары · Биcтро гастрономик",
        "note": "Судак, угорь, сезонные овощи региона · Меню от €49",
        "michelin": "guide", "starred": False
    },
    "r_auberge_16": {
        "name": "L'Auberge (праздничный ужин)", "city": "Les Sources de Cheverny (в отеле)",
        "date": "20250716", "date_ru": "16 июля 🎉",
        "emoji": "🏨", "rating": 4.7, "reviews": 620,
        "price_pp": 55, "cuisine": "Биcтрономия · Дровая печь",
        "note": "Праздничный ужин в отеле · Bib Gourmand · Можно попросить особый стол",
        "michelin": "bib", "starred": False
    },
    "r_berthelot": {
        "name": "Berthelot", "city": "Amboise (~40 км от отеля)",
        "date": "20250715", "date_ru": "15 июля (альт.)",
        "emoji": "🏰", "rating": 4.7, "reviews": 892,
        "price_pp": 45, "cuisine": "Изысканная французская",
        "note": "9.8/10 на TheFork · Лучший в Амбуазе",
        "michelin": None, "starred": False
    },
    "r_epicurien": {
        "name": "L'Épicurien", "city": "Amboise (~40 км от отеля)",
        "date": "20250715", "date_ru": "15 июля (альт.)",
        "emoji": "🏰", "rating": 4.6, "reviews": 678,
        "price_pp": 45, "cuisine": "Творческая французская",
        "note": "22 места · Уютный переулок · Нестандартные сочетания",
        "michelin": None, "starred": False
    },
    # ── Орлеан · 17 июля ─────────────────────────────────────────────────────
    "r7": {
        "name": "Le Lift", "city": "Orleans",
        "date": "20250717", "date_ru": "17 июля",
        "emoji": "🏙️", "rating": 4.6, "reviews": 643,
        "price_pp": 55, "cuisine": "Авторская · Икра Osciètre",
        "note": "Панорама на Луару · Меню от €44",
        "michelin": "guide", "starred": False
    },
    # ── Исключены из фильтра (только для справки) ────────────────────────────
    "_christophe_hay": {
        "name": "Christophe Hay", "city": "Blois",
        "date": "20250715", "date_ru": "—",
        "emoji": "🚫", "rating": 4.8, "reviews": 743,
        "price_pp": 180, "cuisine": "Haute cuisine",
        "note": "Исключён: ★★ Michelin и цена >€70",
        "michelin": "star2", "starred": True
    },
    "_favori": {
        "name": "Le Favori", "city": "Les Sources de Cheverny",
        "date": "20250716", "date_ru": "—",
        "emoji": "🚫", "rating": 4.9, "reviews": 580,
        "price_pp": 150, "cuisine": "Гастрономическая",
        "note": "Исключён: ★ Michelin и цена >€70",
        "michelin": "star1", "starred": True
    },
}

# ── ЗАМКИ (без изменений) ─────────────────────────────────────────────────────
CASTLES = {
    "cheverny":   {"name": "Château de Cheverny",           "emoji": "🦌", "lat": 47.5000, "lon": 1.4570, "tickets": "chateau-cheverny.fr",   "must_book": False, "rating": 4.6, "price": "€13"},
    "chambord":   {"name": "Château de Chambord",           "emoji": "🏰", "lat": 47.6162, "lon": 1.5170, "tickets": "domaine-chambord.org",   "must_book": False, "rating": 4.6, "price": "€15"},
    "blois":      {"name": "Château Royal de Blois",        "emoji": "🏛️", "lat": 47.5861, "lon": 1.3359, "tickets": "chateaudeblois.fr",      "must_book": False, "rating": 4.2, "price": "€14"},
    "chaumont":   {"name": "Château de Chaumont-sur-Loire", "emoji": "🌿", "lat": 47.4790, "lon": 1.1812, "tickets": "domaine-chaumont.fr",    "must_book": False, "rating": 4.4, "price": "€24"},
    "chenonceau": {"name": "Château de Chenonceau",         "emoji": "🌉", "lat": 47.3248, "lon": 1.0703, "tickets": "chenonceau.com",         "must_book": True,  "rating": 4.8, "price": "€16"},
    "amboise":    {"name": "Château Royal d'Amboise",       "emoji": "👑", "lat": 47.4130, "lon": 0.9836, "tickets": "chateau-amboise.com",    "must_book": False, "rating": 4.6, "price": "€16"},
    "clos_luce":  {"name": "Château du Clos Lucé",          "emoji": "🎨", "lat": 47.4108, "lon": 0.9831, "tickets": "vinci-closluce.com",     "must_book": False, "rating": 4.7, "price": "€18"},
}

PLAN = {
    1: {"label": "День 1 — 15 июля",
        "stops": [("🦌","Cheverny","09:30","~3 км · 🚲 велосипед от отеля"),
                  ("🏰","Chambord","11:30","~20 км · 🚗 25 мин · онлайн-билет рекомендован"),
                  ("🏛️","Blois",   "15:00","~20 км · 🚗 25 мин от Chambord")],
        "dinner": "🐟 Au Rendez-vous des Pêcheurs — в Блуа, после замка (📖 Guide Michelin)"},
    2: {"label": "День 2 — 16 июля",
        "stops": [("🌉","Chenonceau","09:00","~37 км · 🚗 45 мин · ⚠️ ОНЛАЙН-БИЛЕТ: chenonceau.com"),
                  ("👑","Amboise",   "13:30","~40 км · 🚗 20 мин от Chenonceau"),
                  ("🎨","Clos Lucé", "15:00","0.5 км пешком от Amboise")],
        "dinner": "🏨 L'Auberge — в вашем отеле (🍽️ Bib Gourmand) · Праздничный ужин!"},
}

# ── ВСПОМОГАТЕЛЬНЫЕ ───────────────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2) -> int:
    R = 6371; r = math.radians
    a = (math.sin((r(lat2)-r(lat1))/2)**2
         + math.cos(r(lat1))*math.cos(r(lat2))*math.sin((r(lon2)-r(lon1))/2)**2)
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def thefork_url(name, city, date, covers):
    return f"https://www.thefork.fr/search?q={urllib.parse.quote(name+' '+city)}&date={date}&covers={covers}"

def is_hotel(key): return key in ("r_auberge", "r_auberge_16")

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖  Спросить AI-помощника",    callback_data="ai_mode")],
        [InlineKeyboardButton("🍽️  Подобрать ресторан",       callback_data="f_reviews")],
        [InlineKeyboardButton("🏰  Маршрут по замкам",        callback_data="castle_plan")],
        [InlineKeyboardButton("📍  Все замки рядом с отелем", callback_data="castle_all")],
        [InlineKeyboardButton("📅  Наш маршрут",              callback_data="itinerary")],
    ])

async def ask_claude(msg: str) -> str:
    system = """Ты AI-помощник для поездки по Франции (июль 2025).
Маршрут: Этрета (11.07) → Трувиль (12-14.07) → Les Sources de Cheverny (14-17.07) → Орлеан (17.07).
Бюджет ресторанов: не более €70/чел, БЕЗ звёзд Michelin.
Рекомендованные рестораны:
• 11.07: Le 1635 / Restaurant du Casino (Этрета)
• 12.07: Les Mouettes (📖 Guide Michelin); 13.07: Le Noroit (Трувиль)
• 14.07: L'Auberge в отеле (🍽️ Bib Gourmand) — открыт на День Бастилии
• 15.07: Au Rendez-vous des Pêcheurs в Блуа (📖 Guide Michelin, €49 меню)
• 16.07: L'Auberge в отеле (праздничный ужин)
• 17.07: Le Lift в Орлеане (📖 Guide Michelin)
Замки от ближнего: Cheverny(3км 🚲)→Chambord(20км)→Blois(20км)→Chaumont(23км)→Chenonceau(37км⚠️)→Amboise(40км)→Clos Lucé(40км)
Отвечай по-русски, кратко (3-5 предложений), практично."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_KEY,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-sonnet-4-6", "max_tokens": 500,
                      "system": system, "messages": [{"role": "user", "content": msg}]})
            return r.json()["content"][0]["text"]
    except Exception as e:
        return f"⚠️ Ошибка AI: {e}"

# ── HANDLERS ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.update({"min_reviews": 0, "min_rating": 0.0,
                               "max_price": 70, "ai_mode": False})
    await update.message.reply_text(
        "🇫🇷 *Путеводитель: Нормандия → Луара*\n\n"
        "🏨 Жильё 14–17 июля: *Les Sources de Cheverny* (5★)\n"
        "💰 Фильтр: до *€70/чел* · Без звёзд Michelin\n"
        "📖 Michelin-статус отображается на каждом ресторане\n\n"
        "Что хотите сделать?",
        reply_markup=main_kb(), parse_mode="Markdown")


async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    d = q.data; ud = context.user_data

    # ── Меню ─────────────────────────────────────────────────────────────────
    if d == "main_menu":
        ud["ai_mode"] = False
        await q.edit_message_text("🇫🇷 *Путеводитель*\n\nЧто хотите сделать?",
                                  reply_markup=main_kb(), parse_mode="Markdown")

    # ── AI ────────────────────────────────────────────────────────────────────
    elif d == "ai_mode":
        ud["ai_mode"] = True
        await q.edit_message_text(
            "🤖 *AI-помощник активирован*\n\n"
            "Задайте любой вопрос о поездке:\n"
            "• Что есть в Этрета кроме скал?\n"
            "• Открыты ли рестораны 14 июля?\n"
            "• Чем отличается Bib Gourmand от звезды?\n"
            "• Какой замок посмотреть первым?\n\n"
            "_Напишите вопрос ↓_",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")]]),
            parse_mode="Markdown")

    # ── Фильтр 1: ОТЗЫВЫ ─────────────────────────────────────────────────────
    elif d == "f_reviews":
        cur = ud.get("min_reviews", 0)
        kb = []
        for lbl, v in [("Любое кол-во", 0), ("500+ отзывов", 500),
                        ("1 000+ отзывов", 1000), ("2 000+ отзывов", 2000)]:
            kb.append([InlineKeyboardButton(lbl + (" ✅" if v == cur else ""),
                                            callback_data=f"rev_{v}")])
        kb.append([InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")])
        await q.edit_message_text(
            "💬 *Шаг 1/3 — Минимальное кол-во отзывов:*\n\n"
            "_⭐ Звёздные рестораны Michelin исключены автоматически_",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("rev_"):
        ud["min_reviews"] = int(d[4:])
        cur = ud.get("min_rating", 0.0)
        kb = []
        for lbl, v in [("Любой рейтинг", 0.0), ("4.0+ ⭐", 4.0),
                        ("4.3+ ⭐⭐", 4.3), ("4.5+ ⭐⭐⭐", 4.5)]:
            kb.append([InlineKeyboardButton(lbl + (" ✅" if v == cur else ""),
                                            callback_data=f"rat_{v}")])
        kb.append([InlineKeyboardButton("◀ Кол-во отзывов", callback_data="f_reviews")])
        await q.edit_message_text(
            f"💬 Отзывов: *{ud['min_reviews']:,}+* ✅\n\n"
            f"⭐ *Шаг 2/3 — Минимальный рейтинг:*",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("rat_"):
        ud["min_rating"] = float(d[4:])
        cur = ud.get("max_price", 70)
        kb = []
        for lbl, v in [("до €50/чел", 50), ("до €60/чел", 60), ("до €70/чел", 70)]:
            kb.append([InlineKeyboardButton(lbl + (" ✅" if v == cur else ""),
                                            callback_data=f"price_{v}")])
        kb.append([InlineKeyboardButton("◀ Рейтинг", callback_data=f"rev_{ud['min_reviews']}")])
        await q.edit_message_text(
            f"⭐ Рейтинг: *{ud['min_rating']}+* ✅\n\n"
            f"💰 *Шаг 3/3 — Максимальная цена на человека:*\n"
            f"_Без алкоголя, ужин 3 блюда_",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("price_"):
        ud["max_price"] = int(d[6:])
        await _show_restaurants(q, ud)

    # ── Список ───────────────────────────────────────────────────────────────
    elif d == "relist":
        await _show_restaurants(q, ud)

    elif d.startswith("res_"):
        key = d[4:]; ud["restaurant"] = key; r = RESTAURANTS[key]
        badge = michelin_badge(r["michelin"])
        kb = [
            [InlineKeyboardButton(t, callback_data=f"time_{t}") for t in ["19:00","19:30","20:00"]],
            [InlineKeyboardButton(t, callback_data=f"time_{t}") for t in ["20:30","21:00","21:30"]],
            [InlineKeyboardButton("◀ Другой ресторан", callback_data="relist")],
        ]
        await q.edit_message_text(
            f"{r['emoji']} *{r['name']}*{badge}\n"
            f"📍 {r['city']}\n"
            f"📅 {r['date_ru']}  ·  ⭐ {r['rating']}  ·  💬 {r['reviews']:,} отз.\n"
            f"💰 ~€{r['price_pp']}/чел  ·  {r['cuisine']}\n"
            f"ℹ️ _{r['note']}_\n\n"
            f"🕐 Выберите время ужина:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("time_"):
        ud["time"] = d[5:]
        kb = [
            [InlineKeyboardButton(p, callback_data=f"ppl_{p}") for p in "1234"],
            [InlineKeyboardButton(p, callback_data=f"ppl_{p}") for p in "5678"],
            [InlineKeyboardButton("◀ Другое время",
                                  callback_data=f"res_{ud.get('restaurant','r2')}")],
        ]
        await q.edit_message_text(
            f"🕐 Время: *{ud['time']}*\n\n👥 Сколько гостей?",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("ppl_"):
        ud["people"] = d[4:]; await _show_booking(q, ud)

    # ── Замки ─────────────────────────────────────────────────────────────────
    elif d == "castle_plan": await _show_plan(q)
    elif d == "castle_all":  await _show_all_castles(q)

    # ── Маршрут ───────────────────────────────────────────────────────────────
    elif d == "itinerary":
        kb = [
            [InlineKeyboardButton("🍽️ Подобрать ресторан", callback_data="f_reviews")],
            [InlineKeyboardButton("🏰 План замков",        callback_data="castle_plan")],
            [InlineKeyboardButton("◀ Главное меню",        callback_data="main_menu")],
        ]
        await q.edit_message_text(
            "📅 *Маршрут с ресторанами (≤€70/чел):*\n\n"
            "🌊 *11 июля* — Этрета\n"
            "   Le 1635 / Restaurant du Casino\n\n"
            "🏖️ *12 июля* — Трувиль\n"
            "   Les Mouettes 📖 Guide Michelin\n\n"
            "🏖️ *13 июля* — Трувиль\n"
            "   Le Noroit\n\n"
            "🏨 *14 июля* 🎆 — Заезд в Les Sources de Cheverny\n"
            "   L'Auberge в отеле 🍽️ Bib Gourmand\n"
            "   _(Le Favori ★ закрыт пн–вт)_\n\n"
            "🏰 *15 июля* — Замки: Шеверни→Шамбор→Блуа\n"
            "   Au Rendez-vous des Pêcheurs 📖 Guide Michelin\n"
            "   _(в Блуа, после замка, €49 меню)_\n\n"
            "🏰 *16 июля* — Замки: Шенонсо→Амбуаз→Кло-Люсе\n"
            "   L'Auberge в отеле 🍽️ Bib Gourmand 🎉\n\n"
            "🏙️ *17 июля* — Орлеан\n"
            "   Le Lift 📖 Guide Michelin",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ── ЭКРАНЫ ────────────────────────────────────────────────────────────────────

async def _show_restaurants(q, ud):
    mr = ud.get("min_rating", 0.0)
    mv = ud.get("min_reviews", 0)
    mp = ud.get("max_price", 70)

    ok = {k: v for k, v in RESTAURANTS.items()
          if not v["starred"]          # без звёзд
          and not k.startswith("_")    # не служебные записи
          and v["rating"] >= mr
          and v["reviews"] >= mv
          and v["price_pp"] <= mp}
    ok_sorted = sorted(ok.items(), key=lambda x: -x[1]["rating"])

    if not ok_sorted:
        kb = [[InlineKeyboardButton("🔄 Сбросить фильтры", callback_data="f_reviews")],
              [InlineKeyboardButton("◀ Главное меню",      callback_data="main_menu")]]
        await q.edit_message_text(
            "😔 *Нет ресторанов по этим критериям.*\nСнизьте требования.",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    header = (f"🍽️ *Рестораны* (найдено: {len(ok_sorted)})\n"
              f"_💬 {mv:,}+  ·  ⭐ {mr}+  ·  💰 ≤€{mp}/чел  ·  без ★ Michelin_\n\n"
              f"🍽️ Bib Gourmand  ·  📖 Guide Michelin  ·  (нет значка) — не в Michelin")
    kb = []
    for key, r in ok_sorted:
        badge = michelin_badge(r["michelin"])
        kb.append([InlineKeyboardButton(
            f"{r['emoji']} {r['name']}{badge} — €{r['price_pp']}/чел · "
            f"⭐{r['rating']} ({r['reviews']:,}✉) · {r['date_ru']}",
            callback_data=f"res_{key}")])
    kb += [
        [InlineKeyboardButton("🔧 Изменить фильтры", callback_data="f_reviews")],
        [InlineKeyboardButton("◀ Главное меню",      callback_data="main_menu")],
    ]
    await q.edit_message_text(header, reply_markup=InlineKeyboardMarkup(kb),
                              parse_mode="Markdown")


async def _show_booking(q, ud):
    key = ud.get("restaurant", "r2"); time = ud.get("time", "20:00")
    ppl = ud.get("people", "2");      r = RESTAURANTS[key]
    badge = michelin_badge(r["michelin"])
    url   = (f"https://www.{HOTEL['site']}" if is_hotel(key)
             else thefork_url(r["name"], r["city"], r["date"], ppl))
    label = ("🔗 Бронировать на сайте отеля →" if is_hotel(key)
             else "🔗 Открыть TheFork и забронировать →")
    kb = [
        [InlineKeyboardButton(label, url=url)],
        [InlineKeyboardButton("🤖 Спросить AI",    callback_data="ai_mode")],
        [InlineKeyboardButton("🍽️ Другой ресторан", callback_data="relist")],
        [InlineKeyboardButton("◀ Главное меню",    callback_data="main_menu")],
    ]
    await q.edit_message_text(
        f"📋 *Данные для бронирования:*\n\n"
        f"{r['emoji']} *{r['name']}*{badge}\n"
        f"📍 {r['city']}\n"
        f"📅 {r['date_ru']}  ·  💰 ~€{r['price_pp']}/чел\n"
        f"⭐ {r['rating']}  ·  💬 {r['reviews']:,} отзывов\n"
        f"🕐 {time}  ·  👥 {ppl} гост.\n\n"
        f"ℹ️ _{r['note']}_\n\n"
        f"👇 Нажмите для бронирования!",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def _show_plan(q):
    lines = [f"🏰 *2-ДНЕВНЫЙ МАРШРУТ*\n🏨 Старт: *Les Sources de Cheverny*\n"]
    for n, day in PLAN.items():
        lines.append(f"*━━ {day['label']} ━━*")
        for e, name, t, info in day["stops"]:
            lines.append(f"{e} *{t}* — {name}\n   _{info}_")
        lines.append(f"\n{day['dinner']}\n")
    lines.append(
        "🎟 *Билеты онлайн (⚠️ обязательно):*\n"
        "• Шенонсо: chenonceau.com\n"
        "• Шамбор: domaine-chambord.org\n"
        "• Амбуаз: chateau-amboise.com")
    kb = [
        [InlineKeyboardButton("📍 Все замки с км",    callback_data="castle_all")],
        [InlineKeyboardButton("🤖 Спросить AI",       callback_data="ai_mode")],
        [InlineKeyboardButton("◀ Главное меню",       callback_data="main_menu")],
    ]
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                              parse_mode="Markdown", disable_web_page_preview=True)


async def _show_all_castles(q):
    rows = sorted([(haversine(HOTEL["lat"], HOTEL["lon"], c["lat"], c["lon"]), k, c)
                   for k, c in CASTLES.items()])
    lines = [f"📍 *Замки от Les Sources de Cheverny*\n"]
    for dist, key, c in rows:
        flag = " ⚠️ _онлайн-билет!_" if c["must_book"] else ""
        lines.append(f"{c['emoji']} *{c['name']}* — {dist} км{flag}\n"
                     f"   ⭐ {c['rating']} · {c['price']} · {c['tickets']}\n")
    kb = [
        [InlineKeyboardButton("🗓 2-дневный план",   callback_data="castle_plan")],
        [InlineKeyboardButton("◀ Главное меню",      callback_data="main_menu")],
    ]
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                              parse_mode="Markdown", disable_web_page_preview=True)


# ── AI HANDLER ────────────────────────────────────────────────────────────────
async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("ai_mode", False):
        await update.message.reply_text("Напишите /start для меню, или нажмите «Спросить AI».")
        return
    thinking = await update.message.reply_text("🤖 _Думаю..._", parse_mode="Markdown")
    answer = await ask_claude(update.message.text)
    await thinking.delete()
    await update.message.reply_text(
        f"🤖 *AI:*\n\n{answer}\n\n_Задайте ещё вопрос или /start_",
        parse_mode="Markdown")


# ── ЗАПУСК ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_handler))
    print("✅ Бот v5 запущен (≤€70/чел · Michelin-бейджи · Без звёзд)")
    app.run_polling()
