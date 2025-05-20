import json
import os
import random
import asyncio
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Fayl va foydalanuvchi statistikasi
file_usage_count = defaultdict(int)
unique_users = set()

# Foydalanuvchi statistikasi va test savollari
user_stats = {}
user_tests = {}
user_answers = {}

TEST_FOLDER = "tests"
QUESTION_INTERVAL = 10  # soniyada

def load_test_files():
    return [f for f in os.listdir(TEST_FOLDER) if f.endswith(".json")]

def load_test_data(file_name):
    with open(os.path.join(TEST_FOLDER, file_name), "r", encoding="utf-8") as f:
        return json.load(f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    unique_users.add(user_id)

    files = load_test_files()
    if not files:
        await update.message.reply_text("Hech qanday test topilmadi.")
        return

    selected_file = random.choice(files)
    file_usage_count[selected_file] += 1

    test_data = load_test_data(selected_file)
    questions = random.sample(test_data, len(test_data))

    user_stats[user_id] = {"name": update.effective_user.full_name, "correct": 0, "wrong": 0}
    user_tests[user_id] = questions
    user_answers[user_id] = 0

    await update.message.reply_text(f"🧪 {selected_file.replace('.json', '')} test boshlandi!")
    await send_next_question(update, context)

async def send_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_tests or user_answers[user_id] >= len(user_tests[user_id]):
        stats = user_stats[user_id]
        await update.message.reply_text(
            f"✅ Test yakunlandi!\nTo‘g‘ri javoblar: {stats['correct']}\nNoto‘g‘ri javoblar: {stats['wrong']}"
        )
        return

    q = user_tests[user_id][user_answers[user_id]]
    question_text = f"{user_answers[user_id]+1}. {q['savol']}\n"
    for i, opt in enumerate(q['variantlar'], 1):
        question_text += f"{i}. {opt}\n"

    reply_markup = ReplyKeyboardMarkup(
        [[str(i + 1) for i in range(len(q['variantlar']))]], one_time_keyboard=True, resize_keyboard=True
    )

    await update.message.reply_text(question_text, reply_markup=reply_markup)

    await asyncio.sleep(QUESTION_INTERVAL)

    # Avto o'tkazish
    user_answers[user_id] += 1
    await send_next_question(update, context)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_tests or user_answers[user_id] == 0:
        return

    q_index = user_answers[user_id] - 1
    question = user_tests[user_id][q_index]

    try:
        user_choice = int(update.message.text.strip()) - 1
    except ValueError:
        return

    if 0 <= user_choice < len(question['variantlar']):
        if user_choice == question['javob']:
            user_stats[user_id]["correct"] += 1
        else:
            user_stats[user_id]["wrong"] += 1

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📈 Umumiy statistika:\n"
    msg += f"👥 Foydalanuvchilar soni: {len(unique_users)}\n\n"

    if not file_usage_count:
        msg += "🗂 Hali hech qanday test ishlatilmagan."
    else:
        msg += "📂 Fayllar bo‘yicha foydalanish soni:\n"
        sorted_files = sorted(file_usage_count.items(), key=lambda x: x[1], reverse=True)
        for filename, count in sorted_files:
            msg += f"• {filename.replace('.json', '')}: {count} marta\n"

    await update.message.reply_text(msg)

if __name__ == '__main__':
    app = ApplicationBuilder().token("BOT_TOKENINGIZNI_BU_YERGA_QO'YING").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stat", show_statistics))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_answer))

    print("✅ Bot ishga tushdi.")
    app.run_polling()
