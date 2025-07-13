import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import sqlite3
import os
from dotenv import load_dotenv

# .env fayldan tokenni olish
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

# Loglama sozlash
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation holatlari
ADD_NAME, ADD_PHONE, ADD_PROFESSION, ADD_REGION = range(4)
SEARCH = 0

# Ma'lumotlar bazasini yaratish
def init_db():
    conn = sqlite3.connect('contacts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS contacts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  phone TEXT NOT NULL,
                  profession TEXT,
                  region TEXT)''')
    conn.commit()
    conn.close()

# Kontakt qo'shish
def add_contact(name, phone, profession, region):
    conn = sqlite3.connect('contacts.db')
    c = conn.cursor()
    c.execute("INSERT INTO contacts (name, phone, profession, region) VALUES (?, ?, ?, ?)",
              (name, phone, profession, region))
    conn.commit()
    conn.close()

# Hudud/kasb bo'yicha qidirish
def search_contacts(region=None, profession=None):
    conn = sqlite3.connect('contacts.db')
    c = conn.cursor()

    if region and profession:
        c.execute("SELECT * FROM contacts WHERE region=? AND profession=?", (region, profession))
    elif region:
        c.execute("SELECT * FROM contacts WHERE region=?", (region,))
    elif profession:
        c.execute("SELECT * FROM contacts WHERE profession=?", (profession,))
    else:
        c.execute("SELECT * FROM contacts")

    results = c.fetchall()
    conn.close()
    return results

# Unikal region va profession
def get_regions():
    conn = sqlite3.connect('contacts.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT region FROM contacts WHERE region IS NOT NULL")
    regions = [row[0] for row in c.fetchall()]
    conn.close()
    return regions

def get_professions():
    conn = sqlite3.connect('contacts.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT profession FROM contacts WHERE profession IS NOT NULL")
    professions = [row[0] for row in c.fetchall()]
    conn.close()
    return professions

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        rf"Salom {user.mention_html()}! Men kontaktlarni boshqaruvchi botman.",
        reply_markup=main_menu_keyboard(user.id)
    )

def main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("➕ Kontakt qo'shish", callback_data='add_contact')],
        [InlineKeyboardButton("🔍 Kontakt qidirish", callback_data='search_contacts')],
        [InlineKeyboardButton("📍 Hudud bo'yicha qidirish", callback_data='search_by_region')],
        [InlineKeyboardButton("👨‍⚕️ Kasb bo'yicha qidirish", callback_data='search_by_profession')]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🛠 Admin panel", callback_data='admin_panel')])
    return InlineKeyboardMarkup(keyboard)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Bosh menyu:",
        reply_markup=main_menu_keyboard(query.from_user.id)
    )

# Qo'shish funksiyalari
async def add_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Kontakt ismini kiriting:")
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Telefon raqamini kiriting:")
    return ADD_PHONE

async def add_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Kasbini kiriting:")
    return ADD_PROFESSION

async def add_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['profession'] = update.message.text
    await update.message.reply_text("Hududni (shahar/tuman) kiriting:")
    return ADD_REGION

async def add_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['region'] = update.message.text
    add_contact(
        context.user_data['name'],
        context.user_data['phone'],
        context.user_data['profession'],
        context.user_data['region']
    )
    await update.message.reply_text("✅ Kontakt muvaffaqiyatli qo'shildi!", reply_markup=main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("❌ Sizda admin huquqlari mavjud emas.")
        return
    contacts = search_contacts()
    message = f"📊 Umumiy kontaktlar soni: {len(contacts)}"
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data='main_menu')]
    ]))

# Qidiruv menyulari
async def search_contacts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Qidirish turini tanlang:", reply_markup=search_menu_keyboard())

def search_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📍 Hudud bo'yicha", callback_data='search_by_region')],
        [InlineKeyboardButton("👨‍⚕️ Kasb bo'yicha", callback_data='search_by_profession')],
        [InlineKeyboardButton("🔍 Barcha kontaktlar", callback_data='all_contacts')],
        [InlineKeyboardButton("◀️ Orqaga", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def search_by_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    regions = get_regions()
    if not regions:
        await query.edit_message_text("Hozircha hech qanday hudud qo'shilmagan.")
        return
    keyboard = [[InlineKeyboardButton(region, callback_data=f'region_{region}')]
                for region in regions]
    keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data='search_contacts')])
    await query.edit_message_text("Hududni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def search_by_profession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    professions = get_professions()
    if not professions:
        await query.edit_message_text("Hozircha hech qanday kasb qo'shilmagan.")
        return
    keyboard = [[InlineKeyboardButton(prof, callback_data=f'profession_{prof}')]
                for prof in professions]
    keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data='search_contacts')])
    await query.edit_message_text("Kasbni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_region_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region = query.data.split('_', 1)[1]
    contacts = search_contacts(region=region)
    if not contacts:
        await query.edit_message_text(f"❌ {region} hududida kontakt topilmadi.", reply_markup=back_to_search_keyboard())
        return
    message = f"📍 {region} hududidagi kontaktlar:\n\n"
    for c in contacts:
        message += f"👤 {c[1]}\n📞 {c[2]}\n💼 {c[3]}\n🌍 {c[4]}\n\n"
    await query.edit_message_text(message, reply_markup=back_to_search_keyboard())

async def show_profession_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    profession = query.data.split('_', 1)[1]
    contacts = search_contacts(profession=profession)
    if not contacts:
        await query.edit_message_text(f"❌ {profession} kasbidagi kontakt topilmadi.", reply_markup=back_to_search_keyboard())
        return
    message = f"👨‍⚕️ {profession} kasbidagi kontaktlar:\n\n"
    for c in contacts:
        message += f"👤 {c[1]}\n📞 {c[2]}\n💼 {c[3]}\n🌍 {c[4]}\n\n"
    await query.edit_message_text(message, reply_markup=back_to_search_keyboard())

async def show_all_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    contacts = search_contacts()
    if not contacts:
        await query.edit_message_text("❌ Kontaktlar mavjud emas.", reply_markup=back_to_search_keyboard())
        return
    message = "📋 Barcha kontaktlar:\n\n"
    if len(contacts) > 10:
        contacts = contacts[-10:]
        message = "📋 So'ngi 10 kontakt:\n\n"
    for c in contacts:
        message += f"👤 {c[1]}\n📞 {c[2]}\n💼 {c[3]}\n🌍 {c[4]}\n\n"
    if len(contacts) >= 10:
        message += "⚠️ Faqat so'ngi 10 kontakt ko'rsatilmoqda."
    await query.edit_message_text(message, reply_markup=back_to_search_keyboard())

def back_to_search_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Qidiruv menyusiga", callback_data='search_contacts')],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data='main_menu')]
    ])

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('❌ Bekor qilindi.', reply_markup=main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_contact_start, pattern='^add_contact$')],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_phone)],
            ADD_PROFESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_profession)],
            ADD_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_region)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(main_menu, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(search_contacts_menu, pattern='^search_contacts$'))
    application.add_handler(CallbackQueryHandler(search_by_region, pattern='^search_by_region$'))
    application.add_handler(CallbackQueryHandler(search_by_profession, pattern='^search_by_profession$'))
    application.add_handler(CallbackQueryHandler(show_region_contacts, pattern='^region_'))
    application.add_handler(CallbackQueryHandler(show_profession_contacts, pattern='^profession_'))
    application.add_handler(CallbackQueryHandler(show_all_contacts, pattern='^all_contacts$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))

    application.run_polling()

if __name__ == '__main__':
    main()
