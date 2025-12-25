import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Bot sozlamalari
TOKEN = "7717385229:AAEkN1k5784HVtzX0cxLj-Rxs1qmWyJGxxk"
ADMIN_ID = None  # Birinchi /start bosgan odam admin bo'ladi (yoki qo'lda kiritish mumkin)

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Ma'lumotlar bazasini sozlash
def init_db():
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            score INTEGER,
            total INTEGER,
            percentage REAL,
            finish_time TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    conn.commit()
    conn.close()

# Savollar ro'yxati (Namuna sifatida)
QUIZ_QUESTIONS = [
    {
        "question": "O'zbekistonning poytaxti qaysi shahar?",
        "options": ["Samarqand", "Toshkent", "Buxoro", "Xiva"],
        "correct": 1  # Toshkent
    },
    {
        "question": "Alisher Navoiy nechanchi yilda tug'ilgan?",
        "options": ["1441", "1451", "1341", "1541"],
        "correct": 0  # 1441
    },
    {
        "question": "Dunyo bo'yicha eng ko'p sotilgan kitob qaysi?",
        "options": ["Garri Potter", "Injil", "Don Kixot", "Kichkina shahzoda"],
        "correct": 1  # Injil
    }
]

# FSM holatlari
class QuizStates(StatesGroup):
    answering = State()

# Bot va Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Ma'lumotlar bazasi bilan ishlash funksiyalari
def add_user(user_id, username, full_name):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)', 
                   (user_id, username, full_name))
    conn.commit()
    conn.close()

def set_admin(user_id):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_admin():
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE is_admin = 1')
    admin = cursor.fetchone()
    conn.close()
    return admin[0] if admin else None

def has_finished(user_id):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM results WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_result(user_id, score, total, percentage):
    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO results (user_id, score, total, percentage, finish_time) VALUES (?, ?, ?, ?, ?)',
                   (user_id, score, total, percentage, finish_time))
    conn.commit()
    conn.close()

# Handlerlar
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    user_id = message.from_user.id
    if user_id != get_admin():
        return

    conn = sqlite3.connect('quiz_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.full_name, u.username, r.score, r.total, r.percentage, r.finish_time 
        FROM results r 
        JOIN users u ON r.user_id = u.user_id
        ORDER BY r.percentage DESC, r.finish_time ASC
    ''')
    results = cursor.fetchall()
    conn.close()if not results:
        await message.answer("Hozircha natijalar yo'q.")
        return

    text = "📊 Barcha natijalar (Reyting):\n\n"
    for i, res in enumerate(results, 1):
        text += f"{i}. {res[0]} (@{res[1]}) - {res[2]}/{res[3]} ({res[4]:.1f}%) - {res[5]}\n"
    
    # Agar matn juda uzun bo'lsa, bo'lib yuboramiz
    if len(text) > 4096:
        for x in range(0, len(text), 4096):
            await message.answer(text[x:x+4096])
    else:
        await message.answer(text)

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    add_user(user_id, username, full_name)

    # Birinchi foydalanuvchini admin qilish
    current_admin = get_admin()
    if current_admin is None:
        set_admin(user_id)
        await message.answer("Siz bot admini sifatida tayinlandingiz! Natijalar sizga yuboriladi.")
    
    if has_finished(user_id):
        await message.answer("Siz allaqachon test topshirgansiz. Qayta topshirish imkoniyati yo'q.")
        return

    if not username:
        await message.answer("⚠️ Diqqat! Sizda Telegram 'username' (nik) o'rnatilmagan.\n\n"
                             "Shaffoflikni ta'minlash uchun faqat username'i bor foydalanuvchilar test topshira oladi. "
                             "Iltimos, Telegram sozlamalaridan o'zingizga username yarating va keyin qayta /start bosing.")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="Testni boshlash", callback_data="start_quiz")
    
    await message.answer(
        f"Assalomu alaykum, {full_name}!\n\n"
        f"“Kitobsevarlar” kanalining quiz botiga xush kelibsiz.\n"
        f"Test {len(QUIZ_QUESTIONS)} ta savoldan iborat. Omad!",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "start_quiz")
async def start_quiz(callback: types.CallbackQuery, state: FSMContext):
    if has_finished(callback.from_user.id):
        await callback.answer("Siz allaqachon test topshirgansiz.", show_alert=True)
        return

    await state.update_data(current_question=0, score=0)
    await send_question(callback.message, 0)
    await callback.answer()

async def send_question(message: types.Message, question_index: int):
    question_data = QUIZ_QUESTIONS[question_index]
    
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(question_data["options"]):
        builder.button(text=option, callback_data=f"ans_{i}")
    builder.adjust(1)

    text = f"Savol {question_index + 1}/{len(QUIZ_QUESTIONS)}:\n\n{question_data['question']}"
    
    if message.reply_markup: # Agar bu callbackdan kelgan bo'lsa, tahrirlaymiz
        await message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_q = data.get("current_question", 0)
    score = data.get("score", 0)
    
    selected_option = int(callback.data.split("_")[1])
    
    # To'g'ri javobni tekshirish (lekin foydalanuvchiga aytmaslik)
    if selected_option == QUIZ_QUESTIONS[current_q]["correct"]:
        score += 1
    
    next_q = current_q + 1
    
    if next_q < len(QUIZ_QUESTIONS):
        await state.update_data(current_question=next_q, score=score)
        await send_question(callback.message, next_q)
    else:
        # Quiz tugadi
        total = len(QUIZ_QUESTIONS)
        percentage = (score / total) * 100
        
        save_result(callback.from_user.id, score, total, percentage)
        
        await callback.message.edit_text("Quiz yakunlandi. Sizning natijangiz qayd etildi.")# Adminga xabar yuborish
        admin_id = get_admin()
        if admin_id:
            finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            admin_text = (
                f"🔔 Yangi natija!\n\n"
                f"👤 Ism: {callback.from_user.full_name}\n"
                f"🆔 ID: {callback.from_user.id}\n"
                f"🏷 Username: @{callback.from_user.username}\n"
                f"✅ To'g'ri javoblar: {score}/{total}\n"
                f"📊 Foiz: {percentage:.1f}%\n"
                f"⏰ Vaqt: {finish_time}"
            )
            try:
                await bot.send_message(admin_id, admin_text)
            except Exception as e:
                logging.error(f"Adminga xabar yuborishda xatolik: {e}")
        
        await state.clear()
    
    await callback.answer()

async def main():
    init_db()
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
