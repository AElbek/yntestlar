import json
import random
import asyncio
import os
from dotenv import load_dotenv
from telegram.constants import ParseMode
from telegram import Update, Poll, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, PollAnswerHandler,
    MessageHandler, filters, ContextTypes, CallbackQueryHandler
)

# ⬇️ Token va admin ID'larni .env faylidan olish
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

# 📁 Test fayllar va kechikishlar
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

# 📊 Foydalanuvchi holatlari
poll_data = {}
user_stats = {}
user_states = {}
fan_usage_counts = {}

# 🟢 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states.setdefault(user_id, {"active": False, "selected_file": None})
    state = user_states[user_id]

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
    random.shuffle(all_questions)
    delay = test_delays.get(selected_file, 15)
    user_states[user_id] = {
        "active": True,
        "selected_file": selected_file,
        "questions": all_questions,
        "index": 0
    }

    user_stats[user_id] = {"name": update.effective_user.first_name, "correct": 0, "total": 0}
    await update.message.reply_text(f"🧠 Test boshlandi! Har bir savoldan so‘ng {delay} soniya kutiladi.")
    await send_quiz(update.effective_chat.id, user_id, context)

# ⛔ /stop
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states or not user_states[user_id].get("active"):
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

# 📚 /topics
async def topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not test_files:
        await update.message.reply_text("❗ Hech qanday test fayli topilmadi.")
        return

    buttons = [[InlineKeyboardButton(fname.replace(".json", ""), callback_data=f"select:{fname}")] for fname in test_files]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("📚 Fanni tanlang:", reply_markup=markup)

# 🔁 /reload
async def reload_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Siz admin emassiz.")
        return

    load_files()
    await update.message.reply_text("✅ Test va kechikish fayllari qayta yuklandi.")

# 🔘 Callback
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_states.setdefault(user_id, {"active": False, "selected_file": None})
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
        if data.startswith("continue:"):
            await query.edit_message_text("✅ Test davom etmoqda.")
            user_states[user_id]["index"] += 1
            await send_quiz(query.message.chat_id, user_id, context)
        else:
            await query.edit_message_text("⛔ Test to‘xtatildi.")
            user_states[user_id]["active"] = False

# 📤 Savol yuborish
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

    delay = test_delays.get(state["selected_file"], 15)
    if context.job_queue:
        context.job_queue.run_once(
            send_next_question_auto,
            delay,
            data={"poll_id": msg.poll.id, "chat_id": chat_id, "user_id": user_id}
        )

# ⏭️ Avto-yuborish
async def send_next_question_auto(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    poll_id = data["poll_id"]
    chat_id = data["chat_id"]
    user_id = data["user_id"]

    if poll_id in poll_data and user_id not in poll_data[poll_id]["answered_users"]:
        keyboard = InlineKeyboardMarkup([[ 
            InlineKeyboardButton("✅ Davom ettirish", callback_data=f"continue:{user_id}"),
            InlineKeyboardButton("❌ To‘xtatish", callback_data=f"stop:{user_id}")
        ]])
        await context.bot.send_message(chat_id, "⏰ Siz bu savolga javob bermadingiz.\nDavom etamizmi?", reply_markup=keyboard)
        return

    if user_id not in user_states:
        return

    user_states[user_id]["index"] += 1
    await send_quiz(chat_id, user_id, context)

# 🧠 Poll javobi
async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    user_id = update.poll_answer.user.id
    option_ids = update.poll_answer.option_ids

    if poll_id not in poll_data:
        return

    data = poll_data[poll_id]

    if user_id in data["answered_users"]:
        return

    data["answered_users"].add(user_id)

    if user_id not in user_stats:
        user_stats[user_id] = {
            "name": update.poll_answer.user.full_name,
            "correct": 0,
            "total": 0
        }

    if option_ids and option_ids[0] == data["correct_index"]:
        user_stats[user_id]["correct"] += 1

    user_stats[user_id]["total"] += 1

# 📈 /stat
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_stats:
        await update.message.reply_text("⛔ Statistikalar yo‘q.")
        return

    total_users = len(user_stats)
    active_users = sum(1 for s in user_states.values() if s.get("active"))

    msg = f"📊 Foydalanuvchi statistikasi:\n\n"
    msg += f"🧑‍🤝‍🧑 Jami foydalanuvchilar: {total_users}\n"
    msg += f"⚡ Faol foydalanuvchilar: {active_users}\n\n"

    for stat in user_stats.values():
        percent = round(stat["correct"] / stat["total"] * 100) if stat["total"] else 0
        msg += f"• {stat['name']}: {stat['correct']}/{stat['total']} — {percent}%\n"

    if fan_usage_counts:
        msg += "\n📚 Fanlar bo‘yicha test ishlatilishi:\n"
        sorted_fans = sorted(fan_usage_counts.items(), key=lambda x: x[1], reverse=True)
        for fan, count in sorted_fans:
            name = fan.replace(".json", "")
            msg += f"• {name}: {count} marta ishlatilgan\n"

    await update.message.reply_text(msg)

# 🟢 Botni ishga tushurish
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("topics", topics))
    app.add_handler(CommandHandler("reload", reload_data))
    app.add_handler(CommandHandler("stat", show_statistics))
    app.add_handler(PollAnswerHandler(receive_poll_answer))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, topics))

    print("✅ Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
