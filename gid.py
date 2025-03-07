import logging
import os
import json
import telegram
from telegram.error import BadRequest
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

# Глобальные пути к файлам
GLOBAL_ROUTES_FILE = "global_routes.json"

# Загрузка маршрутов из глобального файла
def load_global_routes():
    try:
        with open(GLOBAL_ROUTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Сохранение маршрутов в глобальный файл
def save_global_routes(routes_data):
    with open(GLOBAL_ROUTES_FILE, "w", encoding="utf-8") as f:
        json.dump(routes_data, f, ensure_ascii=False, indent=4)

# Глобальная функция для работы с путями к файлам пользователей
def get_user_data_path(user_id):
    user_dir = f"user_data/{user_id}"
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)  # Создаем директорию пользователя, если она не существует
    return user_dir

# Сохранение маршрутов пользователя в JSON-файл
def save_user_routes(user_id, routes_data):
    user_dir = get_user_data_path(user_id)
    file_path = os.path.join(user_dir, "routes.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(routes_data, f, ensure_ascii=False, indent=4)

# Загрузка маршрутов пользователя из JSON-файла
def load_user_routes(user_id):
    user_dir = get_user_data_path(user_id)
    file_path = os.path.join(user_dir, "routes.json")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Начало работы бота
async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    # Удаляем команду /start
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass  # Если сообщение уже удалено или нельзя его удалить

    # Отправляем информационное сообщение
    info_message = (
        "Добро пожаловать! Этот бот от НеМаршруты поможет вам:\n"
        "• Создавать свои маршруты.\n"
        "• Просматривать маршруты других пользователей.\n"
        "• Оставлять заявки на путешествия.\n"
        "• Просматривать историю ваших поездок и отзывы.\n"
    )
    await update.message.reply_text(info_message)

    # Показываем главное меню
    await main_menu(update, context)

# Главное меню
async def main_menu(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Маршрут", callback_data="маршрут")],
        [InlineKeyboardButton("Поиск", callback_data="поиск")],
        [InlineKeyboardButton("Заявки", callback_data="заявки")],
        [InlineKeyboardButton("История", callback_data="история")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            # Пытаемся удалить предыдущее сообщение
            await update.callback_query.message.delete()
        except Exception:
            # Если сообщение уже удалено или его нет, игнорируем ошибку
            pass

        # Отправляем новое сообщение с главным меню
        await update.callback_query.message.reply_text("Главное меню:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Главное меню:", reply_markup=reply_markup)

# Меню маршрутов
async def routes_menu(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    keyboard = [
        [InlineKeyboardButton("Создать маршрут", callback_data="создать")],
        [InlineKeyboardButton("Мои маршруты", callback_data="мои")],
        [InlineKeyboardButton("Назад", callback_data="назад")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text="Маршруты:", reply_markup=reply_markup)

# Создание нового маршрута
async def create_route(update: Update, context: CallbackContext) -> None:
    query = update.callback_query

    # Ensure the callback_query exists and has a valid message
    if not query or not query.message:
        await update.message.reply_text("Ошибка при создании маршрута. Пожалуйста, попробуйте снова.")
        return

    await query.answer()

    try:
        # Attempt to delete the previous message
        await query.message.delete()
    except Exception:
        pass  # Ignore errors if the message cannot be deleted

    try:
        # Attempt to send the new message
        sent_message = await query.message.reply_text(text="Пожалуйста, отправьте фото для маршрута.")
        # Save the message ID only if the message was successfully sent
        context.user_data["last_message_id"] = sent_message.message_id
    except Exception as e:
        # Log the error and inform the user if sending the message fails
        logging.error(f"Failed to send message: {e}")
        await query.message.reply_text("Произошла ошибка. Пожалуйста, попробуйте снова позже.")
        return

    # Set the state to "photo" for the next step
    context.user_data["state"] = "photo"

# Сохранение маршрутов пользователя в историю с отзывами
def save_user_history(user_id, history_data):
    user_dir = get_user_data_path(user_id)
    history_file = os.path.join(user_dir, "history.json")
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=4)

# Обработка сообщений пользователя
async def handle_message(update: Update, context: CallbackContext) -> None:
    state = context.user_data.get("state")
    review_state = context.user_data.get("review_state")

    if review_state == "writing":  # If the user is writing a review
        index = context.user_data.get("review_route_index")
        user_id = update.effective_user.id

        if index is not None:
            history = load_user_history(user_id)
            if 0 <= index < len(history):
                # Save the review to the route
                save_review_to_route(user_id, index, update.message.text, is_global=False)

                # Clear review state
                context.user_data.pop("review_route_index", None)
                context.user_data.pop("review_state", None)

                # Inform the user that the review has been saved
                await update.message.reply_text("Спасибо! Ваш отзыв сохранен.")

                # Return to the history menu
                await history_menu(update, context)
            else:
                await update.message.reply_text("Ошибка: Индекс маршрута недействителен.")
        else:
            await update.message.reply_text("Ошибка: Индекс маршрута не определен.")
    elif state == "photo":
        # Handle photo submission for creating a new route
        photo_file = await update.message.photo[-1].get_file()
        context.user_data["photo"] = photo_file.file_id
        await update.message.reply_text("Теперь отправьте название маршрута.")
        context.user_data["state"] = "title"
    elif state == "title":
        context.user_data["title"] = update.message.text
        await update.message.reply_text("Отправьте описание маршрута.")
        context.user_data["state"] = "description"
    elif state == "description":
        context.user_data["description"] = update.message.text
        await update.message.reply_text("Укажите цену маршрута.")
        context.user_data["state"] = "price"
    elif state == "price":
        context.user_data["price"] = update.message.text
        await update.message.reply_text("Укажите местоположение маршрута.")
        context.user_data["state"] = "location"
    elif state == "location":
        context.user_data["location"] = update.message.text

        user_id = update.effective_user.id
        route = {
            "photo": context.user_data["photo"],
            "title": context.user_data["title"],
            "description": context.user_data["description"],
            "price": context.user_data["price"],
            "location": context.user_data["location"],
            "reviews": {},  # Initialize an empty reviews dictionary
        }

        # Save the route to global and user files
        global_routes = load_global_routes()
        global_routes.append(route)
        save_global_routes(global_routes)

        user_routes = load_user_routes(user_id)
        user_routes.append(route)
        save_user_routes(user_id, user_routes)

        context.user_data.clear()
        await show_my_routes(update, context)
    else:
        await update.message.reply_text("Неизвестное сообщение.")

# Сохранение нового маршрута (сохраняет в глобальный и личный файлы)
async def save_route(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    route = {
        "photo": context.user_data["photo"],
        "title": context.user_data["title"],
        "description": context.user_data["description"],
        "price": context.user_data["price"],
        "location": context.user_data["location"],
    }

    # Сохраняем маршрут в глобальный файл
    global_routes = load_global_routes()
    global_routes.append(route)
    save_global_routes(global_routes)

    # Сохраняем маршрут в личный файл пользователя
    user_routes = load_user_routes(user_id)
    user_routes.append(route)
    save_user_routes(user_id, user_routes)

    context.user_data.clear()
    await show_my_routes(update, context)

# Отображение моих маршрутов
async def show_my_routes(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    saved_routes = load_user_routes(user_id)

    if not saved_routes:
        await main_menu(update, context)
        return

    context.user_data["route_index"] = 0
    await display_route(update, context, saved_routes)

# Отображение маршрута
async def display_route(update: Update, context: CallbackContext, routes_list: list) -> None:
    index = context.user_data.get("route_index", 0)

    if index >= len(routes_list):
        index = 0
    elif index < 0:
        index = len(routes_list) - 1

    context.user_data["route_index"] = index
    route = routes_list[index]

    text = (
        f"Название: {route['title']}\n"
        f"Описание: {route['description']}\n"
        f"Цена: {route['price']}\n"
        f"Местоположение: {route['location']}"
    )

    keyboard = [
        [
            InlineKeyboardButton("Назад", callback_data="prev_route"),
            InlineKeyboardButton("Вперед", callback_data="next_route"),
        ],
        [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.delete()
        await update.callback_query.message.reply_photo(route["photo"], caption=text, reply_markup=reply_markup)
    else:
        await update.message.reply_photo(route["photo"], caption=text, reply_markup=reply_markup)

# Переключение между маршрутами
async def navigate_route(update: Update, context: CallbackContext, direction: int, routes_list: list) -> None:
    # Ensure 'route_index' exists in context.user_data
    if "route_index" not in context.user_data:
        context.user_data["route_index"] = 0

    # Adjust the index based on the direction
    context.user_data["route_index"] += direction

    # Ensure the index stays within bounds
    if context.user_data["route_index"] >= len(routes_list):
        context.user_data["route_index"] = 0
    elif context.user_data["route_index"] < 0:
        context.user_data["route_index"] = len(routes_list) - 1

    # Display the updated route
    await display_route(update, context, routes_list)

# Отображение маршрутов при поиске
async def show_search_results(update: Update, context: CallbackContext) -> None:
    global_routes = load_global_routes()

    if not global_routes:
        await main_menu(update, context)
        return

    context.user_data["search_index"] = 0
    await display_search_result(update, context, global_routes)

    # Добавление маршрута в заявки
def add_route_to_applications(user_id, route):
    user_dir = get_user_data_path(user_id)  # Получаем путь к папке пользователя
    applications_file = os.path.join(user_dir, "applications.json")  # Формируем путь к файлу заявок

    applications = []
    if os.path.exists(applications_file):  # Если файл существует, загружаем текущие заявки
        with open(applications_file, "r", encoding="utf-8") as f:
            applications = json.load(f)

    applications.append(route)  # Добавляем новый маршрут в список заявок
    with open(applications_file, "w", encoding="utf-8") as f:  # Сохраняем обновленный список
        json.dump(applications, f, ensure_ascii=False, indent=4)

# Удаление маршрута из заявок
def remove_route_from_applications(user_id, route_index):
    user_dir = get_user_data_path(user_id)
    applications_file = os.path.join(user_dir, "applications.json")

    if not os.path.exists(applications_file):
        return

    with open(applications_file, "r", encoding="utf-8") as f:
        applications = json.load(f)

    if 0 <= route_index < len(applications):
        del applications[route_index]
        with open(applications_file, "w", encoding="utf-8") as f:
            json.dump(applications, f, ensure_ascii=False, indent=4)

# Обработка запроса "Путешествовать"
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Добавление маршрута в заявки
async def handle_travel_request(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    search_index = int(query.data.split("_")[1])
    global_routes = load_global_routes()
    route = global_routes[search_index]

    user_id = update.effective_user.id
    add_route_to_applications(user_id, route)

    await query.message.reply_text("Маршрут успешно добавлен в заявки!")
    await main_menu(update, context)

# Отображение маршрутов из результатов поиска
async def display_search_result(update: Update, context: CallbackContext, routes_list: list) -> None:
    # Ensure 'search_index' exists in context.user_data
    if "search_index" not in context.user_data:
        context.user_data["search_index"] = 0

    # Adjust the index if out of bounds
    index = context.user_data["search_index"]
    if index >= len(routes_list):
        index = 0
    elif index < 0:
        index = len(routes_list) - 1
    context.user_data["search_index"] = index

    # Proceed with displaying the route
    route = routes_list[index]

    text = (
        f"Название: {route['title']}\n"
        f"Описание: {route['description']}\n"
        f"Цена: {route['price']}\n"
        f"Местоположение: {route['location']}"
    )

    # Create the keyboard
    keyboard = [
        [
            InlineKeyboardButton("Назад", callback_data="prev_search"),
            InlineKeyboardButton("Вперед", callback_data="next_search"),
        ],
    ]

    # Add the "Отзывы" button if reviews exist
    if route.get("reviews"):
        keyboard.append([InlineKeyboardButton("Отзывы", callback_data=f"search_reviews_{index}")])

    # Add other buttons
    keyboard.extend([
        [InlineKeyboardButton("Путешествовать", callback_data=f"travel_{index}")],
        [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.delete()
        await update.callback_query.message.reply_photo(
            route["photo"], caption=text, reply_markup=reply_markup
        )
    else:
        await update.message.reply_photo(route["photo"], caption=text, reply_markup=reply_markup)

# Загрузка заявок пользователя из JSON-файла
def load_user_applications(user_id):
    user_dir = get_user_data_path(user_id)
    applications_file = os.path.join(user_dir, "applications.json")
    try:
        with open(applications_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Отображение заявок
async def show_applications(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_dir = get_user_data_path(user_id)
    applications_file = os.path.join(user_dir, "applications.json")

    if not os.path.exists(applications_file):
        # Переходим в главное меню, если файл заявок не существует
        await main_menu(update, context)
        return

    # Загружаем заявки пользователя
    applications = load_user_applications(user_id)

    if not applications:
        # Переходим в главное меню, если список заявок пуст
        await main_menu(update, context)
        return

    context.user_data["application_index"] = 0
    await display_application(update, context, applications)

# Отображение одной заявки
async def display_application(update: Update, context: CallbackContext, applications: list) -> None:
    index = context.user_data.get("application_index", 0)

    if index >= len(applications):
        index = 0
    elif index < 0:
        index = len(applications) - 1

    context.user_data["application_index"] = index
    application = applications[index]

    text = (
        f"Название: {application['title']}\n"
        f"Описание: {application['description']}\n"
        f"Цена: {application['price']}\n"
        f"Местоположение: {application['location']}"
    )

    keyboard = [
        [
            InlineKeyboardButton("Назад", callback_data="prev_application"),
            InlineKeyboardButton("Вперед", callback_data="next_application"),
        ],
        [
            InlineKeyboardButton("Подтвердить", callback_data=f"confirm_{index}"),
            InlineKeyboardButton("Отклонить", callback_data=f"reject_{index}"),
        ],
        [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass

        await update.callback_query.message.reply_photo(
            application["photo"], caption=text, reply_markup=reply_markup
        )
    else:
        await update.message.reply_photo(application["photo"], caption=text, reply_markup=reply_markup)

# Обработка подтверждения/отклонения заявки
async def handle_application_action(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    action, index_str = query.data.split("_")
    index = int(index_str)
    user_id = update.effective_user.id

    applications = load_user_applications(user_id)
    
    if 0 <= index < len(applications):
        # Get the selected application
        application = applications.pop(index)  # Remove the application from the list

        # Save the confirmed application to the user's history
        save_route_to_history(user_id, application)

        # Inform the user about the confirmation
        if action == "confirm":
            await query.message.reply_text("Заявка успешно подтверждена и добавлена в историю!")
        elif action == "reject":
            await query.message.reply_text("Заявка успешно отклонена.")

        # Save the updated applications list
        save_user_applications(user_id, applications)

        # Transition to the main menu or show updated history
        if action == "confirm":
            await history_menu(update, context)  # Show history after confirmation
        else:
            await main_menu(update, context)  # Return to main menu after rejection
    else:
        await query.message.reply_text("Ошибка: Индекс заявки недействителен.")
        await main_menu(update, context)

# Сохранение заявок пользователя
def save_user_applications(user_id, applications_data):
    user_dir = get_user_data_path(user_id)
    applications_file = os.path.join(user_dir, "applications.json")

    with open(applications_file, "w", encoding="utf-8") as f:
        json.dump(applications_data, f, ensure_ascii=False, indent=4)

# Загрузка маршрутов пользователя из истории
def load_user_history(user_id):
    user_dir = get_user_data_path(user_id)
    history_file = os.path.join(user_dir, "history.json")

    if not os.path.exists(history_file):
        return []  # Возвращаем пустой список, если файл не существует

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []  # Возвращаем пустой список, если файл поврежден

# Переключение между заявками
async def navigate_applications(update: Update, context: CallbackContext, direction: int) -> None:
    user_id = update.effective_user.id
    user_dir = get_user_data_path(user_id)
    applications_file = os.path.join(user_dir, "applications.json")

    with open(applications_file, "r", encoding="utf-8") as f:
        applications = json.load(f)

    context.user_data["application_index"] += direction
    await display_application(update, context, applications)

# Переключение между результатами поиска
async def navigate_search(update: Update, context: CallbackContext, direction: int) -> None:
    global_routes = load_global_routes()
    context.user_data["search_index"] += direction
    await display_search_result(update, context, global_routes)

# Сохранение маршрута в историю пользователя
def save_route_to_history(user_id, route):
    user_dir = get_user_data_path(user_id)
    history_file = os.path.join(user_dir, "history.json")

    # Load existing history or initialize it if the file doesn't exist
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except json.JSONDecodeError:
            pass  # Handle corrupted file by starting with an empty history

    # Add the new route to the history
    history.append(route)

    # Save the updated history
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

# Меню заявок
async def applications_menu(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    await show_applications(update, context)

# Меню истории
async def history_menu(update: Update, context: CallbackContext) -> None:
    query = update.callback_query

    if query:  # Check if callback_query exists
        await query.answer()
        await query.message.delete()  # Delete the previous message if it's a callback query

    user_id = update.effective_user.id
    history = load_user_history(user_id)

    if not history:
        if query:
            await query.message.reply_text("История пуста.")
        else:
            await update.message.reply_text("История пуста.")
        return

    context.user_data["history_index"] = 0
    await display_history_route(update, context, history)

# Обработка кнопок
async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "маршрут":
        await routes_menu(update, context)
    elif query.data == "поиск":
        await show_search_results(update, context)
    elif query.data == "заявки":
        await applications_menu(update, context)
    elif query.data == "история":
        await history_menu(update, context)
    elif query.data == "назад":
        await main_menu(update, context)
    elif query.data == "создать":
        await create_route(update, context)
    elif query.data == "мои":
        await show_my_routes(update, context)
    elif query.data.startswith("back_to_search_"):
        parts = query.data.split("_")
        if len(parts) >= 3 and parts[2].isdigit():
            index = int(parts[2])
            context.user_data["search_index"] = index
            await show_search_results(update, context)
        else:
            context.user_data.pop("search_index", None)
            await show_search_results(update, context)
    elif query.data in ["prev_route", "next_route"]:
        await navigate_route(
            update, context, -1 if query.data == "prev_route" else 1, load_user_routes(update.effective_user.id)
        )
    elif query.data.startswith("write_review_"):
        index = int(query.data.split("_")[2])
        await request_review(update, context, index)
    elif query.data in ["prev_search", "next_search"]:
        await navigate_search(update, context, -1 if query.data == "prev_search" else 1)
    elif query.data in ["prev_history", "next_history"]:
        await navigate_history(update, context, -1 if query.data == "prev_history" else 1)
    elif query.data.startswith("travel_"):
        await handle_travel_request(update, context)
    elif query.data in ["prev_application", "next_application"]:
        await navigate_applications(update, context, -1 if query.data == "prev_application" else 1)
    elif query.data.startswith("confirm_") or query.data.startswith("reject_"):
        await handle_application_action(update, context)
    elif query.data.startswith("reviews_"):
        index = int(query.data.split("_")[1])
        is_search = "search" in query.data
        await handle_reviews_request(update, context, index, is_search=is_search)
    elif query.data in ["prev_review", "next_review"]:
        direction = -1 if query.data == "prev_review" else 1
        context.user_data["review_index"] = context.user_data.get("review_index", 0) + direction
        if "search_index" in context.user_data:
            global_routes = load_global_routes()
            route = global_routes[context.user_data["search_index"]]
        else:
            user_id = update.effective_user.id
            history = load_user_history(user_id)
            route = history[context.user_data["history_index"]]

        await display_reviews(update, context, route)
    elif query.data == "back_to_route":
        if "search_index" in context.user_data:
            await show_search_results(update, context)
        else:
            user_id = update.effective_user.id
            history = load_user_history(user_id)
            await display_history_route(update, context, history)
    elif query.data == "main_menu":
        await main_menu(update, context)
    elif query.data.startswith("search_reviews_"):
        index = int(query.data.split("_")[2])  # Extract the index from callback_data
        await handle_reviews_request(update, context, index, is_search=True)
    elif query.data.startswith("history_reviews_"):
        index = int(query.data.split("_")[2])  # Extract the index from callback_data
        await handle_reviews_request(update, context, index, is_search=False)
    else:
        # Обработка нераспознанных кнопок
        try:
            await query.edit_message_text(text=f"Неизвестная команда: {query.data}")
        except telegram.error.BadRequest:
            await query.message.reply_text(f"Неизвестная команда: {query.data}")

async def handle_search_reviews_request(update: Update, context: CallbackContext, index: int) -> None:
    global_routes = load_global_routes()

    if not global_routes or index >= len(global_routes):
        await update.callback_query.message.reply_text("Маршрут не найден.")
        return

    route = global_routes[index]
    review = route.get("review", "Отзыв не оставлен")

    text = (
        f"Название: {route['title']}\n"
        f"Отзыв: {review}"
    )

    keyboard = [
        [InlineKeyboardButton("Назад", callback_data=f"back_to_search_{index}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.reply_text(text, reply_markup=reply_markup)

# Отображение одного маршрута из истории
async def display_history_route(update: Update, context: CallbackContext, history: list) -> None:
    index = context.user_data.get("history_index", 0)

    if not history:
        await update.callback_query.message.reply_text("История пуста.")
        return

    if index >= len(history):
        index = 0
    elif index < 0:
        index = len(history) - 1

    context.user_data["history_index"] = index
    route = history[index]

    user_id = update.effective_user.id
    reviews = route.get("reviews", {})
    user_review = reviews.get(str(user_id), "Отзыв не оставлен")

    text = (
        f"Название: {route['title']}\n"
        f"Описание: {route['description']}\n"
        f"Цена: {route['price']}\n"
        f"Местоположение: {route['location']}\n"
        f"Ваш отзыв: {user_review}"
    )

    keyboard = [
        [
            InlineKeyboardButton("Назад", callback_data="prev_history"),
            InlineKeyboardButton("Вперед", callback_data="next_history"),
        ],
        [InlineKeyboardButton("Написать отзыв", callback_data=f"write_review_{index}")],
        [InlineKeyboardButton("Назад в меню", callback_data="main_menu")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass

        await update.callback_query.message.reply_photo(
            route["photo"], caption=text, reply_markup=reply_markup
        )
    else:
        await update.message.reply_photo(route["photo"], caption=text, reply_markup=reply_markup)

# Обновление кнопки "Отзывы"
async def handle_reviews_request(update: Update, context: CallbackContext, index: int, is_search: bool = False) -> None:
    query = update.callback_query
    await query.answer()

    if is_search:
        global_routes = load_global_routes()
        route = global_routes[index]
        context.user_data["search_index"] = index
    else:
        user_id = update.effective_user.id
        history = load_user_history(user_id)
        route = history[index]
        context.user_data["history_index"] = index

    context.user_data["current_route_index"] = index
    context.user_data["review_index"] = 0

    await display_reviews(update, context, route)

# Переключение между маршрутами в истории
async def navigate_history(update: Update, context: CallbackContext, direction: int) -> None:
    user_id = update.effective_user.id
    history = load_user_history(user_id)

    if not history:
        await update.callback_query.message.reply_text("История пуста.")
        return

    current_index = context.user_data.get("history_index", 0)
    new_index = current_index + direction

    # Циклический переход
    if new_index >= len(history):
        new_index = 0
    elif new_index < 0:
        new_index = len(history) - 1

    context.user_data["history_index"] = new_index
    await display_history_route(update, context, history)

# Обработка запроса на написание отзыва
async def request_review(update: Update, context: CallbackContext, index: int) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    history = load_user_history(user_id)

    if not history or index >= len(history):
        await query.message.reply_text("Маршрут не найден.")
        return

    # Check if the user has already written a review
    route = history[index]
    reviews = route.get("reviews", {})
    if str(user_id) in reviews:
        await query.message.reply_text("Вы уже оставили отзыв для этого маршрута.")
        return

    context.user_data["review_route_index"] = index
    context.user_data["review_state"] = "writing"

    await query.message.reply_text("Пожалуйста, напишите ваш отзыв:")


# Сохранение отзыва в маршрут
def save_review_to_route(user_id, route_index, review_text, is_global=False):
    if is_global:
        routes = load_global_routes()
        route = routes[route_index]
    else:
        user_dir = get_user_data_path(user_id)
        history_file = os.path.join(user_dir, "history.json")
        with open(history_file, "r", encoding="utf-8") as f:
            routes = json.load(f)
        route = routes[route_index]

    # Ensure the 'reviews' key exists in the route
    if "reviews" not in route:
        route["reviews"] = {}

    # Save the review with the user ID as the key
    route["reviews"][user_id] = review_text

    if is_global:
        # Save the updated global routes
        save_global_routes(routes)
    else:
        # Save the updated user history
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(routes, f, ensure_ascii=False, indent=4)

    # Update the global routes with the new review (if applicable)
    if not is_global:
        global_routes = load_global_routes()
        for i, global_route in enumerate(global_routes):
            if global_route.get("photo") == route.get("photo"):  # Match by photo ID
                global_routes[i] = route  # Replace the old route with the updated one
                break
        save_global_routes(global_routes)

# Отображение отзывов для маршрута
async def display_reviews(update: Update, context: CallbackContext, route: dict) -> None:
    reviews = route.get("reviews", [])
    if not reviews:
        await update.callback_query.message.reply_text("Отзывы отсутствуют.")
        return

    review_index = context.user_data.get("review_index", 0)
    if review_index >= len(reviews):
        review_index = 0
    elif review_index < 0:
        review_index = len(reviews) - 1
    context.user_data["review_index"] = review_index

    # Display the current review
    text = (
        f"Название маршрута: {route['title']}\n"
        f"Отзыв {review_index + 1}/{len(reviews)}:\n"
        f"{reviews[review_index]}"
    )

    keyboard = [
        [
            InlineKeyboardButton("Назад", callback_data="prev_review"),
            InlineKeyboardButton("Вперед", callback_data="next_review"),
        ],
        [InlineKeyboardButton("Назад к маршруту", callback_data="back_to_route")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.reply_text(text, reply_markup=reply_markup)

# Переключение между отзывами
async def navigate_reviews(update: Update, context: CallbackContext, direction: int) -> None:
    context.user_data["review_index"] = context.user_data.get("review_index", 0)
    context.user_data["review_index"] += direction

    route_index = context.user_data.get("current_route_index")
    if "search_index" in context.user_data:
        global_routes = load_global_routes()
        route = global_routes[route_index]
    else:
        user_id = update.effective_user.id
        history = load_user_history(user_id)
        route = history[route_index]

    await display_reviews(update, context, route)

# Основная функция
def main() -> None:
    token = "7540520199:AAHDILtQfWgv3OrbDkMM5XFfCzX-WNrgvwA"
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()