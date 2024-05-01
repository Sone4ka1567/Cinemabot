import datetime
import sqlite3

from cinema import format_film_name


class Database():
    def __init__(self):
        self.connection = sqlite3.connect("stats.db")
        self.cursor = self.connection.cursor()

    def start(self):
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS " +
            "history(chat_id INT, date DATE, request VARCHAR(256), primary key (chat_id, date))"
        )
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS stats(chat_id INT, film_id INT, film_name VARCHAR(256), count INT,"
            "primary key (chat_id, film_id))"
        )

    def history_db_update(self, message):
        self.connection.execute(
            "INSERT INTO history (chat_id, date, request) VALUES (?, ?, ?)",
            (message.chat.id, datetime.datetime.now(tz=datetime.timezone.utc), message.text)
        )

    def stats_db_update(self, film_id: int, chat_id: int, movie) -> None:
        film_name = format_film_name(movie)

        self.connection.execute(
            """
            INSERT INTO stats (film_id, chat_id, film_name, count)
            VALUES (?, ?, ?, COALESCE((SELECT count FROM stats WHERE film_id = ? AND chat_id = ?) + 1, 1))
            ON CONFLICT(film_id, chat_id) DO UPDATE SET
                count = excluded.count,
                film_name = excluded.film_name;
            """,
            (film_id, chat_id, film_name, film_id, chat_id)
        )

    def get_stats(self, message):
        return self.cursor.execute(
            "SELECT film_name, count FROM stats WHERE chat_id = ? ORDER BY count DESC",
            (message.chat.id,)
        ).fetchall()

    def get_history(self, message):
        return self.cursor.execute(
            "SELECT date, request FROM history WHERE chat_id = ? ORDER BY date DESC",
            (message.chat.id,)
        ).fetchall()

    def finish(self):
        self.cursor.close()
        self.connection.close()
