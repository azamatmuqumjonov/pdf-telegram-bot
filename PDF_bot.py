import telebot
from fpdf import FPDF
import os
from datetime import datetime

# Токен бота
TOKEN = "7422108576:AAGmYfNL9BKnLw_WHJ2CSQkU2y9kK9bT8N4"
ADMIN_ID = 5999342037

bot = telebot.TeleBot(TOKEN)

# Временное хранилище данных
user_data = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, 
        "Привет, я Бот, который делает из твоих фотографий PDF файл. Загрузи фотографии, затем отправь команду /create. Если хочешь сбросить загруженные фотографии, напиши /reset."
    )

@bot.message_handler(commands=['reset'])
def reset_data(message):
    user_id = message.from_user.id
    if user_id in user_data:
        # Удаляем все временные фотографии пользователя
        for photo_path in user_data[user_id].get('photos', {}).values():
            if os.path.exists(photo_path):
                os.remove(photo_path)
        del user_data[user_id]  # Удаляем данные пользователя
        bot.send_message(message.chat.id, "Все загруженные фотографии сброшены!")
    else:
        bot.send_message(message.chat.id, "У вас нет загруженных фотографий для сброса.")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id

    # Создаём структуру для хранения данных, если пользователя ещё нет
    if user_id not in user_data:
        user_data[user_id] = {'photos': {}, 'notified': False, 'album_id': None, 'index': 0}

    # Проверяем, является ли сообщение частью альбома
    album_id = message.media_group_id
    if album_id:
        # Если пришёл новый альбом, сбрасываем уведомление
        if user_data[user_id]['album_id'] != album_id:
            user_data[user_id]['album_id'] = album_id
            user_data[user_id]['notified'] = False
    else:
        # Если альбом отсутствует, сбрасываем album_id
        user_data[user_id]['album_id'] = None

    # Получаем файл с максимальным разрешением
    photo_file_id = message.photo[-1].file_id
    file_info = bot.get_file(photo_file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # Увеличиваем индекс для сохранения порядка
    user_data[user_id]['index'] += 1
    photo_index = user_data[user_id]['index']

    # Генерируем уникальное имя файла
    file_path = f"temp_{user_id}_{photo_index}.jpg"

    # Сохраняем файл
    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    # Добавляем файл с учётом порядка
    user_data[user_id]['photos'][photo_index] = file_path

    # Уведомляем пользователя только если это первое фото в новом альбоме или отдельное фото
    if not user_data[user_id]['notified']:
        bot.reply_to(
            message, 
            "Ваши фото получены! Напишите /create, чтобы создать PDF файл."
        )
        user_data[user_id]['notified'] = True

@bot.message_handler(commands=['create'])
def ask_for_pdf_name(message):
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id]['photos']:
        bot.send_message(message.chat.id, "Ты не загрузил ни одной фотографии!")
        return

    bot.send_message(message.chat.id, "Как назовем твой файл?")
    bot.register_next_step_handler(message, create_pdf)


def create_pdf(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"ID: {user_id}"  # Если username отсутствует, подставляем ID
    current_time = datetime.now().strftime("%H:%M")
    pdf_name = message.text.strip()  # Получаем название от пользователя

    if not pdf_name:
        bot.send_message(message.chat.id, "Название файла не может быть пустым!")
        return

    pdf = FPDF()

    # Сортируем фотографии в порядке их индекса
    photo_paths = [user_data[user_id]['photos'][i] for i in sorted(user_data[user_id]['photos'])]

    total_size = 0
    for photo_path in photo_paths:
        pdf.add_page()
        pdf.image(photo_path, x=10, y=10, w=190)  # Настраивай размеры, если нужно
        
        # Подсчитываем общий размер
        total_size += os.path.getsize(photo_path)

    # Сохраняем PDF
    pdf_path = f"{pdf_name}.pdf"
    pdf.output(pdf_path)

    # Проверяем размер PDF
    pdf_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    if pdf_size_mb > 50:
        with open(pdf_path, 'rb') as pdf_file:
            bot.send_document(
                ADMIN_ID, 
                pdf_file, 
                caption=f"Слишком большой файл от @{username}. Отправляю только администратору."
            )
        bot.send_message(user_id, "PDF-файл превысил 50 МБ. Отправил его только администратору.")
    else:
        # Отправляем PDF пользователю
        with open(pdf_path, 'rb') as pdf_file:
            bot.send_document(user_id, pdf_file, caption=f"Твой PDF файл '{pdf_name}' готов!")

        # Отправляем PDF админу
        with open(pdf_path, 'rb') as pdf_file:
            bot.send_document(
                ADMIN_ID, 
                pdf_file, 
                caption=f"user: @{username}\nвремя: {current_time}"
            )
    
    # Удаляем PDF и временные файлы
    os.remove(pdf_path)
    for photo_path in photo_paths:
        os.remove(photo_path)
    del user_data[user_id]  # Очищаем данные пользователя


if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
