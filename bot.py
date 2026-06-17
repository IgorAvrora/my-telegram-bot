"""
╔══════════════════════════════════════════════════════════╗
║  🇫🇷 FRANCE TRAVEL BOT — ВЕРСИЯ 6                        ║
╠══════════════════════════════════════════════════════════╣
║  Новое в v6:                                             ║
║  • Фильтр по ДАТЕ бронирования (первый шаг)              ║
║  • Топ-5 результатов, приоритет — кол-во отзывов         ║
║  • В каждой карточке: чек/чел · отзывы · рейтинг · гид   ║
║  • Кроме Michelin учитывается Gault&Millau и др. гиды    ║
╠══════════════════════════════════════════════════════════╣
║  Порядок фильтров:                                       ║
║   1) Дата ужина  2) Мин. отзывов  3) Мин. рейтинг        ║
║   4) Макс. цена/чел  →  Топ-5 по кол-ву отзывов          ║
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

# ── ДАТЫ ПОЕЗДКИ ───────────────────────────────────────────────────────────────
DATES = [
    ("20250711", "11 июля — Этрета"),
    ("20250712", "12 июля — Трувиль"),
    ("20250713", "13 июля — Трувиль"),
    ("20250714", "14 июля 🎆 — День Бастилии"),
    ("20250715", "15 июля — Замки Луары"),
    ("20250716", "16 июля 🎉 — Замки Луары"),
    ("20250717", "17 июля — Орлеан"),
]

# ── ГИДЫ ───────────────────────────────────────────────────────────────────────
# michelin: None | "guide" | "bib" | "star1" | "star2"  (звёзды исключаются из выдачи)
# other_guide: текст доп. гида (Gault&Millau и т.п.) или None

def guide_label(r: dict) -> str:
    parts = []
    m = r.get("michelin")
    if m == "bib":   parts.append("🍽️ Michelin Bib Gourmand")
    elif m == "guide": parts.append("📖 Michelin Guide")
    elif m in ("star1","star2"): parts.append("⭐ Michelin Star")
    if r.get("other_guide"):
        parts.append(f"📘 {r['other_guide']}")
    return " · ".join(parts) if parts else "— не в гидах —"

# ── РЕСТОРАНЫ ─────────────────────────────────────────────────────────────────
RESTAURANTS = {
    "r_casino": {
        "name": "Restaurant du Casino JOA", "city": "Etretat", "date": "20250711",
        "emoji": "🌊", "rating": 4.2, "reviews": 523, "price_pp": 50,
        "cuisine": "Французская · Морепродукты",
        "note": "Панорамный вид на море · Элегантная атмосфера",
        "michelin": None, "other_guide": None, "starred": False
    },
    "r_1635": {
        "name": "Le 1635", "city": "Etretat", "date": "20250711",
        "emoji": "🌊", "rating": 4.3, "reviews": 612, "price_pp": 45,
        "cuisine": "Нормандская французская",
        "note": "Аутентичная нормандская кухня · Уютная атмосфера",
        "michelin": None, "other_guide": None, "starred": False
    },
    "r2": {
        "name": "Les Mouettes", "city": "Trouville-sur-Mer", "date": "20250712",
        "emoji": "🏖️", "rating": 4.4, "reviews": 2568, "price_pp": 50,
        "cuisine": "Морепродукты · Нормандская",
        "note": "Рекорд по числу отзывов в Трувиле",
        "michelin": "guide", "other_guide": None, "starred": False
    },
    "r3": {
        "name": "Le Noroit", "city": "Trouville-sur-Mer", "date": "20250713",
        "emoji": "🏖️", "rating": 4.5, "reviews": 1188, "price_pp": 45,
        "cuisine": "Французская · Морепродукты",
        "note": "Любимец местных жителей",
        "michelin": None, "other_guide": "Gault&Millau 12/20", "starred": False
    },
    "r4": {
        "name": "Les Docks", "city": "Trouville-sur-Mer", "date": "20250712",
        "emoji": "🏖️", "rating": 4.5, "reviews": 1064, "price_pp": 45,
        "cuisine": "Морепродукты",
        "note": "Альтернатива Les Mouettes",
        "michelin": None, "other_guide": None, "starred": False
    },
    "r5": {
        "name": "Brasserie Les Bains", "city": "Trouville-sur-Mer", "date": "20250712",
        "emoji": "🏖️", "rating": 4.3, "reviews": 1001, "price_pp": 45,
        "cuisine": "Французская брассери",
        "note": "Историческая элегантная брассери",
        "michelin": None, "other_guide": None, "starred": False
    },
    "r_auberge": {
        "name": "L'Auberge", "city": "Les Sources de Cheverny (отель)", "date": "20250714",
        "emoji": "🏨", "rating": 4.7, "reviews": 620, "price_pp": 50,
        "cuisine": "Биcтрономия · Дровая печь",
        "note": "⚡ Лучший выбор 14 июля — в отеле · открыт на День Бастилии",
        "michelin": "bib", "other_guide": None, "starred": False, "hotel": True
    },
    "r_pecheurs": {
        "name": "Au Rendez-vous des Pêcheurs", "city": "Blois (~20 км от отеля)", "date": "20250715",
        "emoji": "🐟", "rating": 4.5, "reviews": 830, "price_pp": 55,
        "cuisine": "Рыба Луары · Биcтро гастрономик",
        "note": "Судак, угорь, местные овощи · Меню от €49",
        "michelin": "guide", "other_guide": "Gault&Millau 13/20", "starred": False
    },
    "r_berthelot": {
        "name": "Berthelot", "city": "Amboise (~40 км)", "date": "20250715",
        "emoji": "🏰", "rating": 4.7, "reviews": 892, "price_pp": 45,
        "cuisine": "Изысканная французская",
        "note": "9.8/10 на TheFork · Лучший в Амбуазе",
        "michelin": None, "other_guide": None, "starred": False
    },
    "r_epicurien": {
        "name": "L'Épicurien", "city": "Amboise (~40 км)", "date": "20250715",
        "emoji": "🏰", "rating": 4.6, "reviews": 678, "price_pp": 45,
        "cuisine": "Творческая французская",
        "note": "22 места · Уютный переулок",
        "michelin": None, "other_guide": None, "starred": False
    },
    "r_auberge16": {
        "name": "L'Auberge (праздничный)", "city": "Les Sources de Cheverny (отель)", "date": "20250716",
        "emoji": "🏨", "rating": 4.7, "reviews": 620, "price_pp": 55,
        "cuisine": "Биcтрономия · Дровая печь",
        "note": "Праздничный ужин в отеле · Попросить особый стол",
        "michelin": "bib", "other_guide": None, "starred": False, "hotel": True
    },
    "r7": {
        "name": "Le Lift", "city": "Orleans", "date": "20250717",
        "emoji": "🏙️", "rating": 4.6, "reviews": 643, "price_pp": 55,
        "cuisine": "Авторская · Икра Osciètre",
        "note": "Панорама на Луару · Меню от €44",
        "michelin": "guide", "other_guide": None, "starred": False
    },
    # ── Исключены автоматически (звёзды Michelin) ────────────────────────────
    "_christophe_hay": {
        "name": "Christophe Hay", "city": "Blois", "date": "20250715",
        "emoji": "🚫", "rating": 4.8, "reviews": 743, "price_pp": 180,
        "cuisine": "Haute cuisine",
        "note": "Исключён: ★★ Michelin, цена >€70",
        "michelin": "star2", "other_guide": None, "starred": True
    },
    "_favori": {
        "name": "Le Favori", "city": "Les Sources de Cheverny", "date": "20250716",
        "emoji": "🚫", "rating": 4.9, "reviews": 580, "price_pp": 150,
        "cuisine": "Гастрономическая",
        "note": "Исключён: ★ Michelin, цена >€70",
        "michelin": "star1", "other_guide": None, "starred": True
    },
}

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
        "stops": [("🦌","Cheverny","09:30","~3 км · 🚲 от отеля"),
                  ("🏰","Chambord","11:30","~20 км · 🚗 25 мин"),
                  ("🏛️","Blois",   "15:00","~20 км от Chambord")],
        "dinner": "🐟 Au Rendez-vous des Pêcheurs — Блуа (📖 Michelin Guide)"},
    2: {"label": "День 2 — 16 июля",
        "stops": [("🌉","Chenonceau","09:00","~37 км · ⚠️ ОНЛАЙН-БИЛЕТ"),
                  ("👑","Amboise",   "13:30","~40 км · 🚗 20 мин"),
                  ("🎨","Clos Lucé", "15:00","0.5 км пешком от Amboise")],
        "dinner": "🏨 L'Auberge — в отеле (🍽️ Bib Gourmand) 🎉"},
}

# ── ВСПОМОГАТЕЛЬНЫЕ ────────────────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2) -> int:
    R = 6371; r = math.radians
    a = (math.sin((r(lat2)-r(lat1))/2)**2
         + math.cos(r(lat1))*math.cos(r(lat2))*math.sin((r(lon2)-r(lon1))/2)**2)
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def thefork_url(name, city, date, covers):
    return f"https://www.thefork.fr/search?q={urllib.parse.quote(name+' '+city)}&date={date}&covers={covers}"

def is_hotel(key): return RESTAURANTS.get(key, {}).get("hotel", False)

def date_label(date_code):
    for d, lbl in DATES:
        if d == date_code: return lbl
    return date_code

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖  Спросить AI-помощника",    callback_data="ai_mode")],
        [InlineKeyboardButton("🍽️  Подобрать ресторан",       callback_data="f_date")],
        [InlineKeyboardButton("🏰  Маршрут по замкам",        callback_data="castle_plan")],
        [InlineKeyboardButton("📍  Все замки рядом с отелем", callback_data="castle_all")],
        [InlineKeyboardButton("📅  Наш маршрут",              callback_data="itinerary")],
    ])

async def ask_claude(msg: str) -> str:
    system = """Ты AI-помощник для поездки по Франции (июль 2025).
Маршрут: Этрета(11.07)→Трувиль(12-14.07)→Les Sources de Cheverny(14-17.07)→Орлеан(17.07).
Бюджет ресторанов: ≤€70/чел, без звёзд Michelin. Гиды: Michelin Guide/Bib Gourmand, Gault&Millau.
Отвечай по-русски, кратко, практично."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-sonnet-4-6", "max_tokens": 500,
                      "system": system, "messages": [{"role": "user", "content": msg}]})
            return r.json()["content"][0]["text"]
    except Exception as e:
        return f"⚠️ Ошибка AI: {e}"


# ── HANDLERS ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.update({"date": None, "min_reviews": 0, "min_rating": 0.0,
                               "max_price": 70, "ai_mode": False})
    await update.message.reply_text(
        "🇫🇷 *Путеводитель: Нормандия → Луара*\n\n"
        "🏨 Жильё 14–17 июля: *Les Sources de Cheverny*\n"
        "💰 Бюджет: ≤€70/чел · Без звёзд Michelin\n"
        "📖 Показываем гиды: Michelin / Gault&Millau\n\n"
        "Что хотите сделать?",
        reply_markup=main_kb(), parse_mode="Markdown")


async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    d = q.data; ud = context.user_data

    if d == "main_menu":
        ud["ai_mode"] = False
        await q.edit_message_text("🇫🇷 *Путеводитель*\n\nЧто хотите сделать?",
                                  reply_markup=main_kb(), parse_mode="Markdown")

    elif d == "ai_mode":
        ud["ai_mode"] = True
        await q.edit_message_text(
            "🤖 *AI-помощник активирован*\n\nЗадайте вопрос о поездке ↓",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")]]),
            parse_mode="Markdown")

    # ── ШАГ 1: ДАТА ─────────────────────────────────────────────────────────
    elif d == "f_date":
        kb = [[InlineKeyboardButton(lbl, callback_data=f"date_{code}")] for code, lbl in DATES]
        kb.append([InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")])
        await q.edit_message_text(
            "📅 *Шаг 1/4 — На какую дату ищем ресторан?*",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("date_"):
        ud["date"] = d[5:]
        await _ask_reviews(q, ud)

    # ── ШАГ 2: ОТЗЫВЫ ───────────────────────────────────────────────────────
    elif d.startswith("rev_"):
        ud["min_reviews"] = int(d[4:])
        await _ask_rating(q, ud)

    # ── ШАГ 3: РЕЙТИНГ ──────────────────────────────────────────────────────
    elif d.startswith("rat_"):
        ud["min_rating"] = float(d[4:])
        await _ask_price(q, ud)

    # ── ШАГ 4: ЦЕНА → РЕЗУЛЬТАТ ──────────────────────────────────────────────
    elif d.startswith("price_"):
        ud["max_price"] = int(d[6:])
        await _show_results(q, ud)

    elif d == "relist":
        await _show_results(q, ud)

    elif d.startswith("res_"):
        key = d[4:]; ud["restaurant"] = key; r = RESTAURANTS[key]
        kb = [
            [InlineKeyboardButton(t, callback_data=f"time_{t}") for t in ["19:00","19:30","20:00"]],
            [InlineKeyboardButton(t, callback_data=f"time_{t}") for t in ["20:30","21:00","21:30"]],
            [InlineKeyboardButton("◀ Другой ресторан", callback_data="relist")],
        ]
        await q.edit_message_text(
            f"{r['emoji']} *{r['name']}*\n"
            f"📍 {r['city']}\n"
            f"📅 {date_label(r['date'])}\n"
            f"💰 ~€{r['price_pp']}/чел  ·  ⭐ {r['rating']}  ·  💬 {r['reviews']:,} отз.\n"
            f"📖 {guide_label(r)}\n"
            f"🍴 {r['cuisine']}\n"
            f"ℹ️ _{r['note']}_\n\n"
            f"🕐 Выберите время ужина:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("time_"):
        ud["time"] = d[5:]
        kb = [
            [InlineKeyboardButton(p, callback_data=f"ppl_{p}") for p in "1234"],
            [InlineKeyboardButton(p, callback_data=f"ppl_{p}") for p in "5678"],
            [InlineKeyboardButton("◀ Другое время", callback_data=f"res_{ud.get('restaurant')}")],
        ]
        await q.edit_message_text(
            f"🕐 Время: *{ud['time']}*\n\n👥 Сколько гостей?",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("ppl_"):
        ud["people"] = d[4:]; await _show_booking(q, ud)

    elif d == "castle_plan": await _show_plan(q)
    elif d == "castle_all":  await _show_all_castles(q)

    elif d == "itinerary":
        kb = [
            [InlineKeyboardButton("🍽️ Подобрать ресторан", callback_data="f_date")],
            [InlineKeyboardButton("🏰 План замков",        callback_data="castle_plan")],
            [InlineKeyboardButton("◀ Главное меню",        callback_data="main_menu")],
        ]
        await q.edit_message_text(
            "📅 *Маршрут (рестораны ≤€70/чел, без ★):*\n\n"
            "🌊 11 июля — Этрета: Le 1635 / Casino\n"
            "🏖️ 12 июля — Трувиль: Les Mouettes 📖\n"
            "🏖️ 13 июля — Трувиль: Le Noroit\n"
            "🏨 14 июля 🎆 — L'Auberge в отеле 🍽️\n"
            "🏰 15 июля — Au Rdv des Pêcheurs 📖 (Блуа)\n"
            "🏨 16 июля 🎉 — L'Auberge в отеле 🍽️\n"
            "🏙️ 17 июля — Le Lift 📖 (Орлеан)",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ── ШАГИ ФИЛЬТРА ────────────────────────────────────────────────────────────

async def _ask_reviews(q, ud):
    kb = []
    for lbl, v in [("Любое кол-во", 0), ("500+ отзывов", 500),
                    ("1 000+ отзывов", 1000), ("2 000+ отзывов", 2000)]:
        kb.append([InlineKeyboardButton(lbl, callback_data=f"rev_{v}")])
    kb.append([InlineKeyboardButton("◀ Дата", callback_data="f_date")])
    await q.edit_message_text(
        f"📅 Дата: *{date_label(ud['date'])}* ✅\n\n"
        f"💬 *Шаг 2/4 — Минимальное кол-во отзывов:*",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def _ask_rating(q, ud):
    kb = []
    for lbl, v in [("Любой рейтинг", 0.0), ("4.0+ ⭐", 4.0),
                    ("4.3+ ⭐⭐", 4.3), ("4.5+ ⭐⭐⭐", 4.5)]:
        kb.append([InlineKeyboardButton(lbl, callback_data=f"rat_{v}")])
    kb.append([InlineKeyboardButton("◀ Отзывы", callback_data="f_date")])
    await q.edit_message_text(
        f"📅 {date_label(ud['date'])}  ·  💬 {ud['min_reviews']:,}+ ✅\n\n"
        f"⭐ *Шаг 3/4 — Минимальный рейтинг:*",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def _ask_price(q, ud):
    kb = []
    for lbl, v in [("до €50/чел", 50), ("до €60/чел", 60), ("до €70/чел", 70)]:
        kb.append([InlineKeyboardButton(lbl, callback_data=f"price_{v}")])
    kb.append([InlineKeyboardButton("◀ Рейтинг", callback_data="f_date")])
    await q.edit_message_text(
        f"📅 {date_label(ud['date'])}  ·  💬 {ud['min_reviews']:,}+  ·  ⭐ {ud['min_rating']}+ ✅\n\n"
        f"💰 *Шаг 4/4 — Максимальная цена на человека:*\n_Ужин 3 блюда, без напитков_",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ── РЕЗУЛЬТАТЫ: ТОП-5 ПО КОЛ-ВУ ОТЗЫВОВ ───────────────────────────────────────

async def _show_results(q, ud):
    date = ud.get("date")
    mr = ud.get("min_rating", 0.0)
    mv = ud.get("min_reviews", 0)
    mp = ud.get("max_price", 70)

    candidates = [v for k, v in RESTAURANTS.items()
                  if not v["starred"] and not k.startswith("_")
                  and (date is None or v["date"] == date)
                  and v["rating"] >= mr and v["reviews"] >= mv
                  and v["price_pp"] <= mp]

    # Приоритет — количество отзывов (по убыванию), берём топ-5
    candidates.sort(key=lambda r: -r["reviews"])
    top5 = candidates[:5]

    if not top5:
        kb = [[InlineKeyboardButton("🔄 Изменить дату/фильтры", callback_data="f_date")],
              [InlineKeyboardButton("◀ Главное меню",          callback_data="main_menu")]]
        await q.edit_message_text(
            f"😔 *Нет ресторанов на {date_label(date)} по этим критериям.*\n"
            f"Снизьте требования или выберите другую дату.",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    lines = [
        f"🍽️ *Топ-{len(top5)} ресторанов — {date_label(date)}*\n"
        f"_Сортировка: по кол-ву отзывов · Фильтр: 💬{mv:,}+ ⭐{mr}+ 💰≤€{mp}_\n"
    ]
    keys_for_buttons = []
    for i, r in enumerate(candidates if False else top5, 1):
        # находим ключ ресторана
        key = next(k for k, v in RESTAURANTS.items() if v is r)
        keys_for_buttons.append(key)
        lines.append(
            f"\n*{i}. {r['emoji']} {r['name']}*\n"
            f"   💬 {r['reviews']:,} отзывов  ·  ⭐ {r['rating']}\n"
            f"   💰 ~€{r['price_pp']}/чел\n"
            f"   📖 {guide_label(r)}"
        )

    kb = [[InlineKeyboardButton(f"{i}. {RESTAURANTS[k]['name']}", callback_data=f"res_{k}")]
          for i, k in enumerate(keys_for_buttons, 1)]
    kb += [
        [InlineKeyboardButton("🔧 Изменить фильтры", callback_data="f_date")],
        [InlineKeyboardButton("◀ Главное меню",      callback_data="main_menu")],
    ]
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                              parse_mode="Markdown")


async def _show_booking(q, ud):
    key = ud.get("restaurant"); time = ud.get("time", "20:00")
    ppl = ud.get("people", "2"); r = RESTAURANTS[key]
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
        f"📋 *Бронирование готово:*\n\n"
        f"{r['emoji']} *{r['name']}*\n"
        f"📍 {r['city']}  ·  📅 {date_label(r['date'])}\n"
        f"💰 ~€{r['price_pp']}/чел  ·  ⭐ {r['rating']}  ·  💬 {r['reviews']:,} отз.\n"
        f"📖 {guide_label(r)}\n"
        f"🕐 {time}  ·  👥 {ppl} гост.\n\n"
        f"ℹ️ _{r['note']}_\n\n👇 Нажмите для бронирования!",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def _show_plan(q):
    lines = [f"🏰 *2-ДНЕВНЫЙ МАРШРУТ*\n🏨 Старт: *Les Sources de Cheverny*\n"]
    for n, day in PLAN.items():
        lines.append(f"*━━ {day['label']} ━━*")
        for e, name, t, info in day["stops"]:
            lines.append(f"{e} *{t}* — {name}\n   _{info}_")
        lines.append(f"\n{day['dinner']}\n")
    kb = [
        [InlineKeyboardButton("📍 Все замки с км", callback_data="castle_all")],
        [InlineKeyboardButton("◀ Главное меню",    callback_data="main_menu")],
    ]
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                              parse_mode="Markdown", disable_web_page_preview=True)


async def _show_all_castles(q):
    rows = sorted([(haversine(HOTEL["lat"], HOTEL["lon"], c["lat"], c["lon"]), k, c)
                   for k, c in CASTLES.items()])
    lines = [f"📍 *Замки от Les Sources de Cheverny*\n"]
    for dist, key, c in rows:
        flag = " ⚠️ _онлайн!_" if c["must_book"] else ""
        lines.append(f"{c['emoji']} *{c['name']}* — {dist} км{flag}\n   ⭐ {c['rating']} · {c['price']}\n")
    kb = [[InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")]]
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                              parse_mode="Markdown", disable_web_page_preview=True)


async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("ai_mode", False):
        await update.message.reply_text("Напишите /start для меню.")
        return
    thinking = await update.message.reply_text("🤖 _Думаю..._", parse_mode="Markdown")
    answer = await ask_claude(update.message.text)
    await thinking.delete()
    await update.message.reply_text(f"🤖 *AI:*\n\n{answer}", parse_mode="Markdown")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_handler))
    print("✅ Бот v6 запущен (Дата → Топ-5 по отзывам → Гиды)")
    app.run_polling()
