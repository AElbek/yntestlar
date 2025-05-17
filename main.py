import json
import random
import asyncio
import os
from dotenv import load_dotenv
from telegram.constants import ParseMode
from telegram import (
    Update, Poll, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, PollAnswerHandler,
    MessageHandler, filters, ContextTypes, CallbackQueryHandler
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

test_files = {}
test_delays = {}

def load_files():
    global test_files, test_delays
    test_files.clear()
    for filename in os.listdir("."):
        if filename.endswith(".json") and filename != "delays.json":
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    test_files[filename] = json.load(f)
            except Exception as e:
                print(f"⚠️ {filename} faylida xatolik: {e}")
    if os.path.exists("delays.json"):
        with open("delays.json", "r", encoding="utf-8") as f:
            test_delays.update(json.load(f))

load_files()

poll_data = {}
user_stats = {}
user_states = {}
fan_usage_counts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {})

    if not state.get("selected_file"):
        await topics(update, context)
        return

    if state.get("active"):
        await update.message.reply_text("✅ Siz allaqachon testdasiz. Yakunlash uchun /stop ni bosing.")
        return

    selected_file = state["selected_file"]
    all_questions = test_files.get(selected_file, [])
    if not all_questions:
        await update.message.reply_text("❗ Test savollari topilmadi.")
        return

    fan_usage_counts[selected_file] = fan_usage_counts.get(selected_file, 0) + 1

    # Har bir foydalanuvchi uchun savollarni aralashtirib saqlaymiz
    questions = all_questions.copy()
    random.shuffle(questions)
    delay = test_delays.get(selected_file, 15)

    user_states[user_id] = {
        "active": True,
        "selected_file": selected_file,
        "questions": questions,
        "index": 0,
        "delay": delay
    }

    user_stats[user_id] = {"name": update.effective_user.first_name, "correct": 0, "total": 0}
    await update.message.reply_text(f"🧠 Test boshlandi! Har bir savoldan so‘ng {delay} soniya kutiladi.")
    await send_quiz(update.effective_chat.id, user_id, context)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {})

    if not state.get("active"):
        await update.message.reply_text("⛔ Faol test yo‘q.")
        return

    user_states[user_id]["active"] = False
    stat = user_stats.pop(user_id, None)

    if not stat:
        await update.message.reply_text("⚠️ Test statistikasi yo‘q.")
        return

    correct = stat["correct"]
    total = stat["total"]
    percent = round(correct / total * 100) if total > 0 else 0
    await update.message.reply_text(f"✅ Test yakunlandi.\n📊 Natija: {correct}/{total} — {percent}%")
    user_states.pop(user_id, None)

async def topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not test_files:
        await update.message.reply_text("❗ Hech qanday test fayli topilmadi.")
        return

    buttons = [
        [InlineKeyboardButton(fname.replace(".json", ""), callback_data=f"select:{fname}")]
        for fname in test_files
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("📚 Fanni tanlang:", reply_markup=markup)

async def reload_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Siz admin emassiz.")
        return

    load_files()
    await update.message.reply_text("✅ Test va kechikish fayllari qayta yuklandi.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        print(f"⚠️ Callback error: {e}")

    user_id = query.from_user.id
    data = query.data

    if data.startswith("select:"):
        filename = data.split("select:")[1]
        if filename in test_files:
            user_states[user_id] = {"active": False, "selected_file": filename}
            delay = test_delays.get(filename, 15)
            await query.edit_message_text(f"✅ Fan tanlandi: {filename.replace('.json', '')}\n⏱ Delay: {delay} s\n/start ni bosing.")
        else:
            await query.edit_message_text("❌ Fayl topilmadi.")

    elif data.startswith("continue:") or data.startswith("stop:"):
        _, uid = data.split(":")
        if int(uid) != user_id:
            await query.answer("⛔ Bu siz uchun emas.", show_alert=True)
            return

        state = user_states.get(user_id)
        if not state:
            await query.answer("⛔ Sizda faollashtirilgan test yo‘q.", show_alert=True)
            return

        if data.startswith("continue:"):
            await query.edit_message_text("✅ Test davom etmoqda.")
            user_states[user_id]["index"] += 1
            await send_quiz(query.message.chat_id, user_id, context)

        else:  # stop:
            await query.edit_message_text("⛔ Test to‘xtatildi.")
            user_states[user_id]["active"] = False

async def send_quiz(chat_id, user_id, context: ContextTypes.DEFAULT_TYPE):
    state = user_states.get(user_id)
    if not state or not state.get("active"):
        return

    index = state.get("index", 0)
    questions = state.get("questions", [])
    if index >= len(questions):
        await context.bot.send_message(chat_id, "✅ Barcha savollar yakunlandi.")
        user_states[user_id]["active"] = False
        return

    question = questions[index]

    original_options = question["options"]
    correct_index = question["correct_index"]
    correct_answer = original_options[correct_index]

    shuffled_options = original_options.copy()
    random.shuffle(shuffled_options)
    new_correct_index = shuffled_options.index(correct_answer)

    msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"[{index+1}/{len(questions)}] {question['question'][:300]}",
        options=[opt[:100] for opt in shuffled_options],
        type=Poll.QUIZ,
        correct_option_id=new_correct_index,
        is_anonymous=False
    )

    poll_data[msg.poll.id] = {
        "question": question,
        "chat_id": chat_id,
        "user_id": user_id,
        "answered_users": set(),
        "correct_index": new_correct_index
    }

    delay = state.get("delay", 15)
    context.job_queue.run_once(
        send_next_question_auto,
        delay,
        data={"poll_id": msg.poll.id, "chat_id": chat_id, "user_id": user_id}
    )

async def send_next_question_auto(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    poll_id = data["poll_id"]
    chat_id = data["chat_id"]
    user_id = data["user_id"]

    # Foydalanuvchi javob bermagan bo‘lsa
    if poll_id in poll_data and user_id not in poll_data[poll_id]["answered_users"]:
        keyboard = InlineKeyboardMarkup([[ 
            InlineKeyboardButton("✅ Davom ettirish", callback_data=f"continue:{user_id}"),
            InlineKeyboardButton("❌ To‘xtatish", callback_data=f"stop:{user_id}")
        ]])
        await context.bot.send_message(chat_id, "⏰ Siz bu savolga javob bermadingiz.\nDavom etamizmi?", reply_markup=keyboard)
        return

    # Agar foydalanuvchi testni tugatgan bo‘lsa yoki faollashtirilmagan bo‘lsa, qaytish
    if user_id not in user_states or not user_states[user_id].get("active", False):
        return

    user_states[user_id]["index"] += 1
    await send_quiz(chat_id, user_id, context)

async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    user_id = update.poll_answer.user.id
    option_ids = update.poll_answer.option_ids

    if poll_id not in poll_data:
        return

    data = poll_data[poll_id]

    # Faqat poll yaratgan foydalanuvchi javobini qabul qilish uchun:
    if data["user_id"] != user_id:
        return

    if user_id in data["answered_users"]:
        return

    data["answered_users"].add(user_id)

    if user_id not in user_stats:
        user_stats[user_id] = {
            "name": update.poll_answer.user.full_name,
            "correct": 0,
            "total": 0
        }

    correct_index = data["correct_index"]
    user_stats[user_id]["total"] += 1
    if option_ids and option_ids[0] == correct_index:
        user_stats[user_id]["correct"] += 1

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("topics", topics))
    application.add_handler(CommandHandler("reload", reload_data))

    application.add_handler(PollAnswerHandler(receive_poll_answer))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
