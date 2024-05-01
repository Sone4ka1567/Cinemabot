import os

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.files import JSONStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, FSMContext, filters
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor, markdown as md

from tech import Database, texts, MOVIE, PREVIOUS, NEXT, WATCH_MOVIE
from cinema import KinopoiskUnofficialAPI, WatchLinksAPI


bot = Bot(token=os.environ["BOT_API_TOKEN"], parse_mode="MarkdownV2")
storage = JSONStorage('./storage.json')

dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

kinopoisk_unoff_api = KinopoiskUnofficialAPI(token=os.environ["KINOPOISK_API_TOKEN"])
watch_links_api = WatchLinksAPI()

db = Database()


class BotState(StatesGroup):
    choose_movie = State()


def movie_choose_keyboard(movie_index: int, movies_count: int) -> types.InlineKeyboardMarkup:
    has_prev = movie_index > 0
    has_next = movie_index < movies_count - 1

    keyboard = types.InlineKeyboardMarkup(row_width=2)

    if has_prev:
        keyboard.insert(types.InlineKeyboardButton(texts.BACK, callback_data=PREVIOUS))
    if has_next:
        keyboard.insert(types.InlineKeyboardButton(texts.FORWARD, callback_data=NEXT))

    keyboard.row(types.InlineKeyboardButton(texts.LINKS, callback_data=WATCH_MOVIE))

    return keyboard


async def check_message_id(callback: types.CallbackQuery, user_data) -> bool:
    if "message_id" in user_data and callback.message.message_id != user_data["message_id"]:
        await callback.message.answer(texts.PAST_MESSAGES)
        return True

    return False


async def reset_state(message: types.Message, state: FSMContext) -> None:
    user_data = await state.get_data()

    if "keyboard_deleted" in user_data and user_data["keyboard_deleted"] and \
            "message_id" in user_data and user_data["message_id"] is not None:
        await bot.edit_message_reply_markup(message.chat.id, user_data["message_id"], reply_markup=None)
        await state.update_data(keyboard_deleted=True)

    await state.finish()


@dp.message_handler(commands=["start"], state="*")
async def start_command(message: types.Message, state: FSMContext) -> None:
    await reset_state(message, state)
    await message.answer(
        md.text(
            "Привет, {name}\\!".format(name=message.from_user.first_name),
            md.escape_md(texts.START_TEXT),
            sep="\n"
        ),
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.update_data(keyboard_deleted=False)


@dp.message_handler(commands=["help"], state="*")
async def help_command(message: types.Message, state: FSMContext) -> None:
    await reset_state(message, state)
    await message.answer(
        md.escape_md(texts.HELP_TEXT),
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.update_data(keyboard_deleted=False)


@dp.message_handler(commands=["restart"], state="*")
async def restart_command(message: types.Message, state: FSMContext) -> None:
    user_state = await state.get_state()
    if user_state is not None:
        await state.finish()

    await message.answer(md.text(md.escape_md(texts.RESTART)))


@dp.message_handler(commands=["statistics"], state="*")
async def statistics_command(message: types.Message, state: FSMContext) -> None:
    stats = [texts.STATS]
    raw_results = db.get_stats(message)

    for film_name, count in raw_results:
        stats.append("{} : {}\n".format(film_name, count))

    await message.answer(md.escape_md(*stats))


@dp.message_handler(commands=["history"], state="*")
async def history_command(message: types.Message, state: FSMContext) -> None:
    history = [texts.HISTORY]
    raw_results = db.get_history(message)

    for date, request in raw_results:
        str_date = date.split(".")[0]
        history.append("{} : {}\n".format(str_date, request))

    await message.answer(md.escape_md(*history))


@dp.message_handler(content_types=types.ContentType.TEXT, state="*")
async def movies_list(message: types.Message, state: FSMContext) -> None:
    user_state = await state.get_state()
    if user_state is not None:
        await state.finish()

    await message.answer_chat_action(types.ChatActions.TYPING)
    await reset_state(message, state)

    db.history_db_update(message)
    movies = await kinopoisk_unoff_api.find_movie_by_keyword(message.text)

    if len(movies) == 0:
        no_movies_message = md.escape_md(texts.NO_MOVIES)
        await message.answer(no_movies_message)
        return

    await state.reset_data()
    await state.set_state(BotState.choose_movie)
    await state.update_data(movies=movies, movie_index=0)

    picture, info = await kinopoisk_unoff_api.format_for_message(movies[0])
    db.stats_db_update(movies[0]["filmId"],  message.chat.id, movies[0])

    keyboard = movie_choose_keyboard(0, len(movies))
    send = await message.answer_photo(
        types.InputFile.from_url(picture),
        info,
        reply_markup=keyboard
    )
    await state.update_data(keyboard_deleted=False, message_id=send.message_id)


@dp.callback_query_handler(filters.Text(PREVIOUS), state=BotState.choose_movie)
async def previous_movie(callback: types.CallbackQuery, state: FSMContext) -> None:
    user_data = await state.get_data()
    if await check_message_id(callback, user_data):
        return

    movie_index, movies = user_data["movie_index"], user_data["movies"]

    if movie_index <= 0:
        await callback.message.answer(md.escape_md(md.text(texts.NO_PREV)))
        return

    movie_index -= 1
    await state.update_data(movie_index=movie_index)

    picture, info = await kinopoisk_unoff_api.format_for_message(movies[movie_index])
    db.stats_db_update(movies[movie_index]["filmId"], callback.message.chat.id, movies[movie_index])

    keyboard = movie_choose_keyboard(movie_index, len(movies))
    await state.update_data(movies=movies)

    await callback.message.edit_media(
        types.InputMediaPhoto(types.InputFile.from_url(picture), caption=info),
        reply_markup=keyboard
    )
    await state.update_data(keyboard_deleted=False)
    await callback.answer()


@dp.callback_query_handler(filters.Text(NEXT), state=BotState.choose_movie)
async def next_movie(callback: types.CallbackQuery, state: FSMContext) -> None:
    user_data = await state.get_data()
    if await check_message_id(callback, user_data):
        return

    movie_index, movies = user_data["movie_index"], user_data["movies"]

    if movie_index >= len(movies) - 1:
        await callback.message.answer(md.escape_md(md.text(texts.NO_NEXT)))
        return

    movie_index += 1
    await state.update_data(movie_index=movie_index)

    picture, info = await kinopoisk_unoff_api.format_for_message(movies[movie_index])
    db.stats_db_update(movies[movie_index]["filmId"], callback.message.chat.id, movies[movie_index])

    keyboard = movie_choose_keyboard(movie_index, len(movies))
    await state.update_data(movies=movies)

    await callback.message.edit_media(
        types.InputMediaPhoto(types.InputFile.from_url(picture), caption=info),
        reply_markup=keyboard
    )
    await state.update_data(keyboard_deleted=False)
    await callback.answer()


@dp.callback_query_handler(filters.Text(WATCH_MOVIE), state=BotState.choose_movie)
async def watch_movie(callback: types.CallbackQuery, state: FSMContext) -> None:
    user_data = await state.get_data()

    if "keyboard_deleted" in user_data and not user_data["keyboard_deleted"]:
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.update_data(keyboard_deleted=True)

    if await check_message_id(callback, user_data):
        return

    movie = user_data["movies"][user_data["movie_index"]]

    watch_links = await watch_links_api.get_watch_movie_links(movie)
    info = watch_links_api.format_watch_links(movie, watch_links)

    await state.finish()
    await callback.message.answer(info)
    await state.update_data(keyboard_deleted=False)
    await callback.answer()


@dp.message_handler(content_types=types.ContentType.ANY, state="*")
async def wrong_data_format(message: types.Message):
    await message.answer("Я не умею принимать такой формат данных")


@dp.callback_query_handler(filters.Text(startswith=MOVIE))
async def wrong_movie_callback(callback: types.CallbackQuery) -> None:
    await callback.message.answer("Я не могу отвечать на сообщения из прошлого")
    await callback.answer()


@dp.message_handler(state=BotState.choose_movie)
async def internal_server_error(message: types.Message, state: FSMContext) -> None:
    await message.answer(md.text(
            "500 Internal Server Error\n",
            "Try resetting your state"
        ),
        sep="\n"
    )
    await reset_state(message, state)


def main():
    db.start()
    executor.start_polling(dp)
    kinopoisk_unoff_api.session.close()
    watch_links_api.session.close()
    db.finish()


if __name__ == "__main__":
    main()
