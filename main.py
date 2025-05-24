import os
import requests
from dotenv import load_dotenv
import telebot
import mysql.connector
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import re
from datetime import datetime

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

ADMIN_IDS = {1987008784, 1056385081, 756878264}

def get_db_connection():
    """Устанавливает соединение с базой данных MySQL."""
    return mysql.connector.connect(
        host="db4free.net",
        user="vah9i_1",  # ← имя пользователя, которое ты вводил
        password=os.getenv("DB_PASSWORD"),
        database="ivanzolo_1"  # ← имя твоей базы
    )


user_states = {}  # Словарь для хранения состояний пользователей

def get_nickname_from_opendota(steam_id):
    """Получает никнейм из OpenDota API по Steam ID."""
    try:
        response = requests.get(f"https://api.opendota.com/api/players/{steam_id}")
        data = response.json()
        return data.get("profile", {}).get("personaname", None)
    except Exception:
        return None

def menu_keyboard():
    """Возвращает клавиатуру основного меню для обычных пользователей."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row(
        KeyboardButton("🎮 Зарегистрироваться"),
        KeyboardButton("👤 Мой аккаунт")
    )
    markup.row(
        KeyboardButton("📥 Записаться на турнир")
    )
    markup.row(
        KeyboardButton("✏️ Изменить мои данные"),
    )
    markup.row(
        KeyboardButton("🛡️ Техподдержка")
    )
    return markup

def admin_menu_keyboard():
    """Возвращает клавиатуру основного меню для администраторов."""
    markup = menu_keyboard()  # Наследуем обычное меню
    markup.row(
        KeyboardButton("👁 Просмотреть игроков"),
        KeyboardButton("➕ Добавить турнир"),
        KeyboardButton("📊 Записи на турниры")
    )
    markup.row(
        KeyboardButton("⏱ Изменить дату турнира"),
        KeyboardButton("🛠 Обновить данные"),
        KeyboardButton("📂 Просмотр заявок")
    )
    return markup

def cancel_keyboard():
    """Возвращает клавиатуру с кнопкой 'Отмена'."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("❌ Отмена"))
    return markup

def go_to_menu(chat_id, message_text=""):
    """Возвращает пользователя в главное меню."""
    user_states.pop(chat_id, None)  # Очищаем состояние пользователя
    if message_text:
        bot.send_message(chat_id, message_text,
                         reply_markup=menu_keyboard() if chat_id not in ADMIN_IDS else admin_menu_keyboard())
    else:
        bot.send_message(chat_id, "📍 Выберите действие:",
                         reply_markup=menu_keyboard() if chat_id not in ADMIN_IDS else admin_menu_keyboard())

def escape_md(text):
    """Экранирует специальные символы для MarkdownV2."""
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!:\\,:'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

# --- Обработчики Callback-кнопок ---

@bot.callback_query_handler(func=lambda call: call.data == "cancel_action")
def handle_inline_cancel(call):
    """Обрабатывает нажатие на inline-кнопку 'Отмена'."""
    bot.answer_callback_query(call.id)
    go_to_menu(call.message.chat.id, "❌ Действие отменено.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("update_") or call.data.startswith("pos_"))
def handle_user_callbacks(call: CallbackQuery):
    """Обрабатывает callback-кнопки, связанные с обновлением данных пользователя и выбором позиции."""
    user_id = call.message.chat.id
    data = call.data

    if user_id not in user_states:
        bot.answer_callback_query(call.id, "Нет активного действия.")
        go_to_menu(user_id)
        return

    state = user_states[user_id]
    bot.answer_callback_query(call.id)

    if data.startswith("update_"):
        field = data.replace("update_", "")
        state['update_field'] = field
        state['step'] = 'update_value'
        bot.send_message(user_id, f"Введите новое значение для {field}:", reply_markup=cancel_keyboard())

    elif data.startswith("pos_"):
        pos = int(data.replace("pos_", ""))
        state['pos'] = pos
        state['step'] = 'ask_mmr'
        bot.send_message(user_id, "Введите свой MMR (0–16000):", reply_markup=cancel_keyboard())
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_edit_tournament_"))
def handle_admin_tournament_time_edit(call):
    user_id = call.message.chat.id
    tournament_name = call.data.replace("admin_edit_tournament_", "")
    bot.answer_callback_query(call.id)

    user_states[user_id] = {
        'step': 'admin_update_value',
        'update_field': 'registration_time',
        'target_tag': tournament_name
    }

    bot.send_message(user_id, f"Введите новую дату и время для турнира *{escape_md(tournament_name)}* в формате `YYYY-MM-DD HH:MM`:",
                     parse_mode='MarkdownV2', reply_markup=cancel_keyboard())


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_field_"))
def handle_admin_field_choice(call):
    """Обрабатывает выбор поля для обновления админом."""
    user_id = call.message.chat.id
    field = call.data.replace("admin_field_", "")
    bot.answer_callback_query(call.id)

    if user_id not in user_states or 'target_tag' not in user_states[user_id]:
        bot.send_message(user_id, "❌ Ошибка: пользователь для обновления не выбран. Попробуйте снова.")
        go_to_menu(user_id)
        return

    user_states[user_id]['update_field'] = field
    user_states[user_id]['step'] = 'admin_update_value'
    bot.send_message(user_id, f"Введите новое значение для {field} пользователя {user_states[user_id]['target_tag']}:",
                     reply_markup=cancel_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_edit_tag_"))
def handle_admin_tag_choice(call):
    """Обрабатывает выбор пользователя для редактирования админом."""
    user_id = call.message.chat.id
    tag = call.data.replace("admin_edit_tag_", "")
    bot.answer_callback_query(call.id)

    user_states[user_id] = {'step': 'admin_update_field_choice', 'target_tag': tag}

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Steam ID", callback_data="admin_field_IDSTEM"),
        InlineKeyboardButton("Никнейм", callback_data="admin_field_namestem")
    )
    markup.row(
        InlineKeyboardButton("Позиция", callback_data="admin_field_POS"),
        InlineKeyboardButton("MMR", callback_data="admin_field_MMR")
    )
    markup.add(InlineKeyboardButton("Discord", callback_data="admin_field_Discord"))
    markup.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))

    bot.send_message(
        user_id,
        f"Выбран объект: *{escape_md(tag)}*\nЧто изменить?",
        reply_markup=markup,
        parse_mode='MarkdownV2'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("join_tournament_"))
def handle_tournament_join(call):
    """Обрабатывает запись пользователя на турнир."""
    user_id = call.message.chat.id
    username = f"@{call.from_user.username}" if call.from_user.username else f"id{user_id}"
    tournament_id = int(call.data.replace("join_tournament_", ""))
    bot.answer_callback_query(call.id)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Проверяем, зарегистрирован ли пользователь [cite: 13]
        cursor.execute("SELECT COUNT(*) FROM acc WHERE ds = %s", (username,))
        if cursor.fetchone()[0] == 0:
            bot.send_message(user_id,
                             "⛔ Вы не зарегистрированы. Пожалуйста, сначала зарегистрируйтесь через кнопку '🎮 Зарегистрироваться'.")
            go_to_menu(user_id)
            return

        # Проверяем, записан ли уже на этот турнир [cite: 14]
        cursor.execute("SELECT COUNT(*) FROM tournament_players WHERE player_ds = %s AND tournament_id = %s",
                       (username, tournament_id))
        if cursor.fetchone()[0] > 0:
            bot.send_message(user_id, "❗ Вы уже записались на этот турнир.")
            go_to_menu(user_id)
            return

        # Записываем на турнир [cite: 15]
        cursor.execute("INSERT INTO tournament_players (tournament_id, player_ds) VALUES (%s, %s)",
                       (tournament_id, username))
        conn.commit()

        # Получаем название турнира для ответа [cite: 16]
        cursor.execute("SELECT tournament FROM turnaments WHERE id = %s", (tournament_id,))
        tournament_name = cursor.fetchone()[0]

        bot.send_message(user_id, f"✅ Вы успешно записались на турнир: *{escape_md(tournament_name)}*\\.",
                         parse_mode='MarkdownV2')
        go_to_menu(user_id)

    except Exception as e:
        bot.send_message(user_id, f"❌ Ошибка при записи на турнир: {e}")
        go_to_menu(user_id)
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_"))
def handle_reply_to_support_request(call):
    user_id = call.message.chat.id
    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ У тебя нет доступа.")
        return

    request_id = int(call.data.replace("reply_", ""))
    bot.answer_callback_query(call.id)

    user_states[user_id] = {'step': 'waiting_admin_reply', 'request_id': request_id}
    bot.send_message(user_id, f"✍️ Введите ответ для заявки #{request_id}:", reply_markup=cancel_keyboard())

# --- Основные обработчики текстовых сообщений ---

@bot.message_handler(commands=['start', 'menu'])
def main_menu(message):
    """Обрабатывает команды /start и /menu, показывает главное меню."""
    user_states.pop(message.chat.id, None)
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "📍 Выберите действие:", reply_markup=admin_menu_keyboard())
    else:
        bot.send_message(message.chat.id, "📍 Выберите действие:", reply_markup=menu_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_reply_buttons(message):
    """Основной обработчик текстовых сообщений от кнопок и пользователя."""
    user_id = message.chat.id
    text = message.text.strip()
    username = f"@{message.from_user.username}" if message.from_user.username else f"id{user_id}"

    if text == "❌ Отмена":
        go_to_menu(user_id, "❌ Действие отменено.")
        return

    # Обработка состояний, если пользователь находится в "диалоге" с ботом
    if user_id in user_states:
        state = user_states[user_id]

        # Состояние: ожидание названия турнира (админ) [cite: 20]
        if state.get('step') == 'waiting_tournament_name':
            state['tournament_name'] = text
            state['step'] = 'waiting_tournament_time'
            bot.send_message(user_id, "🕒 Введите дату и время начала турнира в формате YYYY-MM-DD HH:MM:")

        # Этап 2: пользователь вводит дату и время турнира
        elif state.get('step') == 'waiting_tournament_time':
            tournament_name = state['tournament_name']
            start_time = text.strip()

            try:
                datetime.strptime(start_time, "%Y-%m-%d %H:%M")  # валидация

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO turnaments (tournament, registration_time) VALUES (%s, %s)",
                    (tournament_name, start_time)
                )
                conn.commit()

                bot.send_message(user_id,
                                 f"✅ Турнир *{escape_md(tournament_name)}* успешно добавлен на *{escape_md(start_time)}*\\.",
                                 parse_mode="MarkdownV2")
                go_to_menu(user_id)

            except ValueError:
                bot.send_message(user_id, "❌ Неверный формат даты. Используйте формат: YYYY-MM-DD HH:MM")
            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при добавлении турнира: {e}")
                go_to_menu(user_id)
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()

        # Состояние: ожидание Steam ID (регистрация) [cite: 22]
        if state.get('step') == 'ask_dota_id':
            if not text.isdigit():
                bot.send_message(user_id, "❌ Steam ID должен быть числом.")
                return

            steam_id = text
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM acc WHERE IDSTEM = %s", (steam_id,))
                if cursor.fetchone()[0] > 0:
                    bot.send_message(user_id, "❌ Этот Steam ID уже зарегистрирован.")
                    go_to_menu(user_id)
                    return
                cursor.execute("SELECT COUNT(*) FROM acc WHERE ds = %s", (username,))
                if cursor.fetchone()[0] > 0:
                    bot.send_message(user_id, "❌ Вы уже зарегистрировали один аккаунт.")
                    go_to_menu(user_id)
                    return
                cursor.close()
                conn.close()
            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при проверке Steam ID: {e}")
                go_to_menu(user_id)
                return

            nickname = get_nickname_from_opendota(steam_id)
            if not nickname:
                bot.send_message(user_id,
                                 f"❌ Не удалось найти ник. Проверьте Steam ID и убедитесь, что ваш профиль в Steam открыт: https://www.opendota.com/players/{steam_id}")
                return

            state['steam_id'] = steam_id
            state['namestem'] = nickname
            state['ds'] = username
            state['step'] = 'ask_pos'

            markup = InlineKeyboardMarkup()
            for i in range(1, 6):
                markup.add(InlineKeyboardButton(f"Позиция {i}", callback_data=f"pos_{i}"))
            markup.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
            bot.send_message(user_id, f"🔍 Найден ник: *{escape_md(nickname)}*\nВыберите позицию:", reply_markup=markup,
                             parse_mode='MarkdownV2')
            return

        # Состояние: ожидание MMR (регистрация) [cite: 31]
        if state.get('step') == 'ask_mmr':
            if not text.isdigit() or not (0 <= int(text) <= 16000):
                bot.send_message(user_id, "❌ MMR должен быть в пределах 0–16000.")
                return
            state['mmr'] = int(text)
            state['step'] = 'ask_discord'
            bot.send_message(user_id, "📨 Введи свой Discord (пример: Player#1234):", reply_markup=cancel_keyboard())
            return

        # Состояние: ожидание Discord (регистрация) [cite: 32]
        if state.get('step') == 'ask_discord':
            state['discord'] = text
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO acc (IDSTEM, namestem, POS, MMR, ds, Discord) VALUES (%s, %s, %s, %s, %s, %s)",
                    (state['steam_id'], state['namestem'], state['pos'], state['mmr'], state['ds'], state['discord'])
                )
                conn.commit()
                bot.send_message(user_id, "✅ Регистрация завершена!")
                go_to_menu(user_id)
            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при сохранении данных: {e}")
                go_to_menu(user_id)
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()
            return

        # Состояние: ожидание нового значения для пользователя (обычное изменение) [cite: 36]
        if state.get('step') == 'update_value':
            field = state['update_field']
            value = text
            tag = state['telegram_tag']

            if field == 'IDSTEM' and (not value.isdigit() or len(value) < 6):
                bot.send_message(user_id, "❌ Steam ID должен быть числом и достаточно длинным.")
                return
            elif field == 'POS' and (not value.isdigit() or not (1 <= int(value) <= 5)):
                bot.send_message(user_id, "❌ Позиция должна быть от 1 до 5.")
                return
            elif field == 'MMR' and (not value.isdigit() or not (0 <= int(value) <= 16000)):
                bot.send_message(user_id, "❌ MMR должен быть от 0 до 16000.")
                return
            elif field == 'namestem':
                new_nickname = get_nickname_from_opendota(value) if value.isdigit() else value
                if value.isdigit() and not new_nickname:
                    bot.send_message(user_id,
                                     f"❌ Не удалось найти ник по этому Steam ID. Проверьте Steam ID: https://www.opendota.com/players/{value}")
                    return
                value = new_nickname or value

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(f"UPDATE acc SET {field} = %s WHERE ds = %s", (value, tag))
                conn.commit()
                bot.send_message(user_id, f"✅ Данные успешно обновлены: {field} теперь *{escape_md(str(value))}*\\.",
                                 parse_mode='MarkdownV2')
                go_to_menu(user_id)
            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при обновлении данных: {e}")
                go_to_menu(user_id)
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()
            return

        # Состояние: ожидание Discord (быстрое изменение) [cite: 44]
        if state.get('step') == 'set_discord':
            discord = text
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE acc SET Discord = %s WHERE ds = %s", (discord, username))
                conn.commit()
                bot.send_message(user_id, "✅ Discord успешно обновлен.")
                go_to_menu(user_id)
            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при сохранении Discord: {e}")
                go_to_menu(user_id)
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()
            return

        # Состояние: админ выбирает пользователя для обновления [cite: 47]
        if state.get('step') == 'admin_select_user_to_update':
            target_identifier = text.strip()
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT ds FROM acc WHERE ds = %s OR Discord = %s",
                               (target_identifier, target_identifier))
                result = cursor.fetchone()
                if result:
                    target_ds_tag = result[0]
                    user_states[user_id]['target_tag'] = target_ds_tag
                    user_states[user_id]['step'] = 'admin_update_field_choice'

                    markup = InlineKeyboardMarkup()
                    markup.row(
                        InlineKeyboardButton("Steam ID", callback_data="admin_field_IDSTEM"),
                        InlineKeyboardButton("Никнейм", callback_data="admin_field_namestem")
                    )
                    markup.row(
                        InlineKeyboardButton("Позиция", callback_data="admin_field_POS"),
                        InlineKeyboardButton("MMR", callback_data="admin_field_MMR")
                    )
                    markup.add(InlineKeyboardButton("Discord", callback_data="admin_field_Discord"))
                    markup.add(
                        InlineKeyboardButton("Дата начала турнира", callback_data="admin_field_registration_time"))

                    markup.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
                    bot.send_message(user_id, f"Выбран пользователь: *{escape_md(target_ds_tag)}*\nЧто изменить?",
                                     reply_markup=markup, parse_mode='MarkdownV2')
                else:
                    bot.send_message(user_id, "❌ Пользователь с таким Discord тегом или Telegram @username не найден.")
                    go_to_menu(user_id)
            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при поиске пользователя: {e}")
                go_to_menu(user_id)
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()
            return

        # Состояние: админ вводит новое значение для выбранного поля [cite: 55]
        if state.get('step') == 'admin_update_value':
            field = state['update_field']
            tag = state['target_tag']
            value = text

            if field == 'IDSTEM' and (not value.isdigit() or len(value) < 6):
                bot.send_message(user_id, "❌ Steam ID должен быть числом и достаточно длинным.")
                return
            elif field == 'POS' and (not value.isdigit() or not (1 <= int(value) <= 5)):
                bot.send_message(user_id, "❌ Позиция должна быть от 1 до 5.")
                return
            elif field == 'MMR' and (not value.isdigit() or not (0 <= int(value) <= 16000)):
                bot.send_message(user_id, "❌ MMR должен быть от 0 до 16000.")
                return
            elif field == 'namestem':
                new_nickname = get_nickname_from_opendota(value) if value.isdigit() else value
                if value.isdigit() and not new_nickname:
                    bot.send_message(user_id,
                                     f"❌ Не удалось найти ник по этому Steam ID. Проверьте Steam ID: https://www.opendota.com/players/{value}")

                    return
                value = new_nickname or value
            elif field == 'registration_time':
                try:
                    datetime.strptime(value, "%Y-%m-%d %H:%M")
                except ValueError:
                    bot.send_message(user_id, "❌ Неверный формат даты. Используйте YYYY-MM-DD HH:MM")
                    return

                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE turnaments SET registration_time = %s WHERE tournament = %s",
                        (value, tag)
                    )
                    conn.commit()
                    bot.send_message(user_id,
                                     f"✅ Дата турнира *{escape_md(tag)}* обновлена на *{escape_md(value)}*\\.",
                                     parse_mode='MarkdownV2')
                except Exception as e:
                    bot.send_message(user_id, f"❌ Ошибка при обновлении даты турнира: {e}")
                finally:
                    if 'conn' in locals() and conn.is_connected():
                        cursor.close()
                        conn.close()
                go_to_menu(user_id)
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(f"UPDATE acc SET {field} = %s WHERE ds = %s", (value, tag))
                conn.commit()
                bot.send_message(user_id,
                                 f"✅ Данные пользователя *{escape_md(tag)}* успешно обновлены: {field} теперь *{escape_md(str(value))}*\\.",
                                 parse_mode='MarkdownV2')
                go_to_menu(user_id)
            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при обновлении данных пользователя: {e}")
                go_to_menu(user_id)
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()
            return

        # Состояние: админ вводит ответ на заявку в техподдержку [cite: 64]
        if state.get('step') == "waiting_admin_reply":
            request_id = state['request_id']
            reply_text = text

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE support_requests SET reply = %s, replied_at = NOW() WHERE id = %s",
                               (reply_text, request_id))
                conn.commit()

                # Получаем user_id клиента, чтобы отправить ему ответ [cite: 66]
                cursor.execute("SELECT user_id FROM support_requests WHERE id = %s", (request_id,))
                client_id = cursor.fetchone()[0]

                bot.send_message(user_id, f"✅ Ответ на заявку #{request_id} отправлен.")
                try:
                    # Отправляем ответ пользователю [cite: 67]
                    bot.send_message(client_id,
                                     f"📢 *Ответ по вашей заявке #{request_id}:*\n\n__{escape_md(reply_text)}__",
                                     parse_mode='MarkdownV2')
                except Exception as e:
                    bot.send_message(user_id, f"❌ Не удалось отправить ответ клиенту {client_id}: {e}")

            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при отправке ответа на заявку: {e}")
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()
                go_to_menu(user_id)
            return
        # Состояние: ожидание сообщения от пользователя для заявки в техподдержку [cite: 69]
        if state.get('step') == 'waiting_support_message':
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO support_requests (user_id, username, message, created_at) VALUES (%s, %s, %s, NOW())",
                    (user_id, username, text)
                )
                conn.commit()
                bot.send_message(user_id,
                                 "✅ Ваша заявка в техподдержку успешно отправлена. Мы свяжемся с вами как можно скорее.")
                go_to_menu(user_id)
            except Exception as e:
                bot.send_message(user_id, f"❌ Ошибка при создании заявки: {e}")
                go_to_menu(user_id)
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()
            return

    # --- Обработка кнопок основного меню ---

    if text == "🎮 Зарегистрироваться":
        # Проверяем, зарегистрирован ли уже пользователь [cite: 74]
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM acc WHERE ds = %s", (username,))
            if cursor.fetchone()[0] > 0:
                bot.send_message(user_id, "❗ Вы уже зарегистрированы. Вы можете обновить свои данные, если нужно.")
                go_to_menu(user_id)
                return
        except Exception as e:
            bot.send_message(user_id, f"❌ Ошибка при проверке регистрации: {e}")
            go_to_menu(user_id)
            return
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

        user_states[user_id] = {'step': 'ask_dota_id'}
        bot.send_message(user_id, "Введите свой Dota ID (Цыфры в доте):", reply_markup=cancel_keyboard())


    elif text == "👤 Мой аккаунт":
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Получаем данные аккаунта [cite: 78]
            cursor.execute("SELECT IDSTEM, namestem, POS, MMR, Discord FROM acc WHERE ds = %s", (username,))
            result = cursor.fetchone()

            # Получаем турниры, на которые записан пользователь [cite: 78]
            cursor.execute("""
                SELECT t.tournament 
                FROM tournament_players tp
                JOIN turnaments t ON tp.tournament_id = t.id
                WHERE tp.player_ds = %s
            """, (username,))
            tournament_rows = cursor.fetchall()

            tournaments_text = f"\n📅 {escape_md('Не зарегистрирован ни в одном турнире.')}"
            # Default message
            if tournament_rows:
                tournaments = "\n".join(f"▫️ {escape_md(row[0])}" for row in tournament_rows)
                tournaments_text = f"\n📅 \\*Зарегистрирован в турнирах:\\*\n{tournaments}"

            if result:
                # Ensure all dynamic data is escaped
                steam_id_escaped = escape_md(str(result[0]))
                nickname_escaped = escape_md(result[1])
                pos_escaped = escape_md(str(result[2]))
                mmr_escaped = escape_md(str(result[3]))
                discord_escaped = escape_md(result[4] or "Не указан")

                bot.send_message(user_id,
                                 f"""👤 *Твой аккаунт:*\nSteam ID: `{steam_id_escaped}`\nНикнейм: *{nickname_escaped}*\nПозиция: `{pos_escaped}`\nMMR: `{mmr_escaped}`\nDiscord: `{discord_escaped}`{tournaments_text}""",
                                 parse_mode='MarkdownV2')
            else:
                bot.send_message(user_id,
                                 "❌ Данные не найдены. Пожалуйста, зарегистрируйтесь через кнопку '🎮 Зарегистрироваться'.")

        except Exception as e:
            bot.send_message(user_id, f"❌ Ошибка при получении данных аккаунта: {e}")
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()
        go_to_menu(user_id)


    elif text == "📋 Посмотреть турниры":
        show_tournaments(message)

    elif text == "📥 Записаться на турнир":
        choose_tournament(message)

    elif text == "👁 Просмотреть игроков":
        view_players(message)

    elif text == "➕ Добавить турнир" and user_id in ADMIN_IDS:
        user_states[user_id] = {'step': 'waiting_tournament_name'}
        bot.send_message(user_id, "📝 Введите название турнира:", reply_markup=cancel_keyboard())
    elif text == "➕ Добавить турнир" and user_id not in ADMIN_IDS:
        bot.send_message(user_id, "⛔ У тебя нет доступа к этой функции.")
        go_to_menu(user_id)

    elif text == "📊 Записи на турниры":
        show_tournament_entries(message)

    elif text == "✏️ Изменить мои данные":
        # Проверяем, зарегистрирован ли пользователь, прежде чем предложить изменить данные [cite: 86]
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM acc WHERE ds = %s", (username,))
            if cursor.fetchone()[0] == 0:
                bot.send_message(user_id, "⛔ Вы не зарегистрированы. Нечего изменять.")
                go_to_menu(user_id)
                return
        except Exception as e:
            bot.send_message(user_id, f"❌ Ошибка при проверке регистрации: {e}")
            go_to_menu(user_id)
            return
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

        user_states[user_id] = {
            'step': 'update_choice',
            'telegram_tag': username
        }
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("Изменить Steam ID", callback_data="update_IDSTEM"),
            InlineKeyboardButton("Изменить никнейм", callback_data="update_namestem")
        )
        markup.row(
            InlineKeyboardButton("Изменить позицию", callback_data="update_POS"),
            InlineKeyboardButton("Изменить MMR", callback_data="update_MMR")
        )
        markup.row(
            InlineKeyboardButton("Изменить Discord", callback_data="update_Discord")
        )
        markup.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        bot.send_message(user_id, "Выберите, что хотите изменить:", reply_markup=markup)

    elif text == "🛠 Обновить данные" and user_id in ADMIN_IDS:
        user_states[user_id] = {'step': 'admin_select_user_to_update'}
        bot.send_message(user_id,
                         "⚙️ Какой аккаунт вы хотите обновить? Введите *Discord тег* или *Telegram @username* пользователя:",
                         reply_markup=cancel_keyboard(), parse_mode='MarkdownV2')
    elif text == "🛠 Обновить данные" and user_id not in ADMIN_IDS:
        bot.send_message(user_id, "⛔ У тебя нет доступа к этой функции.")
        go_to_menu(user_id)

    elif text == "🛡️ Техподдержка":
        support_request(message)

    elif text == "📂 Просмотр заявок":
        show_support_requests(message)

    elif text == "💬 Указать Discord":
        # Проверяем, зарегистрирован ли пользователь [cite: 92]
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM acc WHERE ds = %s", (username,))
            if cursor.fetchone()[0] == 0:
                bot.send_message(user_id, "⛔ Вы не зарегистрированы. Сначала зарегистрируйтесь.")
                go_to_menu(user_id)
                return
        except Exception as e:
            bot.send_message(user_id, f"❌ Ошибка при проверке регистрации: {e}")
            go_to_menu(user_id)
            return
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

        user_states[user_id] = {
            'step': 'set_discord',
            'telegram_tag': username
        }
        bot.send_message(user_id, "✍️ Введи свой Discord :", reply_markup=cancel_keyboard())
    elif text == "⏱ Изменить дату турнира" and user_id in ADMIN_IDS:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT tournament FROM turnaments")
            tournaments = cursor.fetchall()
            if not tournaments:
                bot.send_message(user_id, "⛔ Нет турниров для редактирования.")
                return

            markup = InlineKeyboardMarkup()
            for (name,) in tournaments:
                markup.add(InlineKeyboardButton(name, callback_data=f"admin_edit_tournament_{name}"))
            markup.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))

            bot.send_message(user_id, "🕒 Выберите турнир для изменения даты:", reply_markup=markup)

        except Exception as e:
            bot.send_message(user_id, f"❌ Ошибка: {e}")
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()


# --- Вспомогательные функции ---

def view_players(message):
    """Показывает список всех игроков (только для админов)."""
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ У тебя нет доступа.")
        go_to_menu(message.chat.id)
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT IDSTEM, namestem, POS, MMR, ds, Discord FROM acc")
        rows = cursor.fetchall()

        if not rows:
            bot.send_message(message.chat.id, "ℹ️ Нет зарегистрированных игроков.")
        else:
            response_text = "*Список игроков:*\n\n"
            for row in rows:
                response_text += f"""👤 Игрок: `{escape_md(row[4])}`
Steam ID: `{escape_md(str(row[0]))}`
Ник: *{escape_md(row[1])}*
Позиция: `{escape_md(str(row[2]))}`
MMR: `{escape_md(str(row[3]))}`
Discord: `{escape_md(row[5] or "Не указан")}`\n\n"""
            bot.send_message(message.chat.id, response_text, parse_mode='MarkdownV2')

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при получении списка игроков: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
        go_to_menu(message.chat.id)


def show_tournaments(message):
    """Показывает список активных турниров."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT tournament FROM turnaments")
        rows = cursor.fetchall()

        if not rows:
            bot.send_message(message.chat.id, "ℹ️ Сейчас нет активных турниров.")
        else:
            text = "📋 *Активные турниры:*\n\n" + "\n".join(f"• *{escape_md(row[0])}*" for row in rows)
            bot.send_message(message.chat.id, text, parse_mode='MarkdownV2')

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при запросе турниров: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
        go_to_menu(message.chat.id)


def show_support_requests(message):
    """Показывает незакрытые заявки в техподдержку (только для админов)."""
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ У тебя нет доступа.")
        go_to_menu(message.chat.id)
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, message, created_at FROM support_requests WHERE reply IS NULL ORDER BY created_at DESC LIMIT 10")
        rows = cursor.fetchall()

        if not rows:
            bot.send_message(message.chat.id, "📭 Нет новых заявок.")
        else:
            bot.send_message(message.chat.id, "*Список незакрытых заявок:*\n", parse_mode='MarkdownV2')
            for row in rows:
                bot.send_message(
                    message.chat.id,
                    f"🆔 \\#{escape_md(str(row[0]))}\n👤 `{escape_md(row[1])}`\n💬 _{escape_md(row[2])}_\n🕒 {escape_md(row[3].strftime('%d.%m.%Y %H:%M'))}",
                    reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton(f"✏️ Ответить \\#{escape_md(str(row[0]))}",
                                             callback_data=f"reply_{row[0]}")
                    ),
                    parse_mode='MarkdownV2'
                )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при получении заявок: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
        go_to_menu(message.chat.id)


def support_request(message):
    """Начинает процесс создания заявки в техподдержку."""
    user_id = message.chat.id
    user_states[user_id] = {'step': 'waiting_support_message'}
    bot.send_message(user_id, "✍️ Опишите свою проблему как можно подробнее. Мы ответим как можно скорее:",
                     reply_markup=cancel_keyboard())


def choose_tournament(message):
    """Предлагает пользователю выбрать турнир для записи."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, tournament FROM turnaments")
        tournaments = cursor.fetchall()

        if not tournaments:
            bot.send_message(message.chat.id, "ℹ️ Сейчас нет активных турниров.")
            go_to_menu(message.chat.id)
            return

        markup = InlineKeyboardMarkup()
        cursor.execute("SELECT id, tournament, registration_time FROM turnaments")
        tournaments = cursor.fetchall()

        for t_id, name, time in tournaments:
            time_str = time.strftime('%Y-%m-%d %H:%M') if time else 'Без времени'
            display_text = f"{name} ({time_str})"
            markup.add(InlineKeyboardButton(display_text, callback_data=f"join_tournament_{t_id}"))

        markup.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        bot.send_message(message.chat.id, "📥 Выберите турнир для записи:", reply_markup=markup)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при получении турниров: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def show_tournament_entries(message):
    """Показывает список записей на каждый турнир (только для админов)."""
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ У тебя нет доступа.")
        go_to_menu(message.chat.id)
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Получаем все турниры [cite: 109]
        cursor.execute("SELECT id, tournament FROM turnaments")
        tournaments = cursor.fetchall()

        if not tournaments:
            bot.send_message(message.chat.id, "ℹ️ Нет созданных турниров.")
            return

        for t_id, name in tournaments:
            cursor.execute("SELECT player_ds FROM tournament_players WHERE tournament_id = %s", (t_id,))
            players = cursor.fetchall()
            player_list = "\n".join(f"\\- {escape_md(p[0])}" for p in players) # Ensure player names are escaped

            if not player_list:
                player_list = "_Никто не записался_"

            bot.send_message(
                message.chat.id,
                f"📊 *{escape_md(name)}*\n{player_list}", # Ensure tournament name is escaped here too
                parse_mode='MarkdownV2'
            )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при получении записей: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
        go_to_menu(message.chat.id)

if __name__ == "__main__":
    print("🤖 Бот запущен...")

    bot.infinity_polling()