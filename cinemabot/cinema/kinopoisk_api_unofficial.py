import typing as tp

import aiohttp

from aiogram.utils.markdown import text, escape_md
from aiogram.utils.text_decorations import markdown_decoration as md


def format_film_name(movie: dict[str, str | int]) -> tp.Any:
    names = ["nameRu", "nameEn", "nameOriginal"]
    return next((movie[name] for name in names if name in movie and movie[name] is not None), "-")


class KinopoiskUnofficialAPI:
    API_URL = "https://kinopoiskapiunofficial.tech/api"

    def __init__(self, token: str) -> None:
        self.token = token
        headers = {
            "ACCEPT": "application/json",
            "X-API-KEY": token
        }
        self.session = aiohttp.ClientSession(headers=headers)

    async def find_movie_by_keyword(self, query: str) -> list[dict[str, str | int]]:
        while True:
            params_ = {"keyword": query}
            async with self.session.get(self.API_URL + "/v2.1/films/search-by-keyword", params=params_) as r:
                if r.status == 404:
                    return []  # have not found any
                r_json = await r.json()
                return [{"filmId": film["filmId"]} for film in r_json["films"]]

    async def get_movie_data(self, movie_id: int) -> dict[str, str | int]:
        while True:
            async with self.session.get(self.API_URL + "/v2.2/films/{id}".format(id=movie_id)) as r:
                r_json = await r.json()
                r_json["countries"] = list(map(lambda country: country["country"], r_json["countries"]))
                r_json["genres"] = list(map(lambda genre: genre["genre"], r_json["genres"]))
                r_json["name"] = format_film_name(r_json)

                return r_json

    @staticmethod
    def get_movie_description(movie: dict[str, str | int]) -> tp.Any:
        if movie["description"] is not None:
            if len(movie["description"]) > 2048 and movie["shortDescription"] is not None:
                return escape_md(movie["shortDescription"] + "\n")
            return escape_md(movie["description"] + "\n")
        return "\n"

    @staticmethod
    def get_movie_years(movie: dict[str, str | int]) -> tp.Any:
        if not movie["serial"]:
            year = movie["year"] if movie["year"] is not None else md.italic("Неизвестно")
            return text(md.bold("Год выхода фильма:"), escape_md(year))

        dates = None
        if movie["startYear"] is not None or movie["endYear"] is not None:
            start_year = movie["startYear"] if movie["startYear"] is not None else md.italic("неизвестно")
            end_year = movie["endYear"] if movie["endYear"] is not None else md.italic("наст. время")

            dates = (f" {start_year}" if start_year == end_year else f" {start_year} - {end_year}")

        dates = dates or md.italic("Неизвестно")
        return text(md.bold("Года выхода сериала:"), escape_md(dates + "\n"))

    @staticmethod
    def get_movie_rating(movie: dict[str, str | int]) -> tp.Any:
        if movie["ratingKinopoisk"] is not None:
            return text(md.bold("Рейтинг на Кинопоиске:"), escape_md(movie["ratingKinopoisk"]) + "\n")
        elif movie["ratingImdb"] is not None:
            return text(md.bold("Рейтинг на Imdb:"), escape_md(movie["ratingImdb"]) + "\n")
        return text(md.bold("Рейтинг не найден\n"))

    @staticmethod
    def get_movie_countries(movie: dict[str, str | int]) -> tp.Any:
        if len(movie["countries"]) > 1:
            return text(md.bold("Страны производства:"), escape_md(", ".join(movie["countries"]) + "\n"))
        if len(movie["countries"]) == 1:
            return text(md.bold("Страна производства:"), escape_md(movie["countries"][0] + "\n"))
        return text(md.bold("Страна производства:"), escape_md(md.italic("Неизвестно\n")))

    @staticmethod
    def get_movie_genres(movie: dict[str, str | int]) -> tp.Any:
        if len(movie["genres"]) > 1:
            return text(md.bold("Жанры фильма:"), escape_md(", ".join(movie["genres"]) + "\n"))
        if len(movie["genres"]) == 1:
            return text(md.bold("Жанр фильма:"), escape_md(movie["genres"][0] + "\n"))
        return text(md.bold("Жанр фильма:"), escape_md(md.italic("Неизвестно\n")))

    @staticmethod
    def get_movie_length(movie: dict[str, str | int]) -> tp.Any:
        if movie["filmLength"] is None:
            return text(md.bold("Длительность:"), escape_md(md.italic("Неизвестно\n")))

        if movie["serial"]:
            return text(md.bold("Длительность серии:"), escape_md(movie["filmLength"], "мин.\n"))
        return text(md.bold("Длительность фильма:"), escape_md(movie["filmLength"], "мин.\n"))

    async def format_for_message(self, movie: dict[str, str | int]) -> tuple[str, str]:
        movie.update(await self.get_movie_data(movie["filmId"]))

        movie_info = [md.bold(escape_md(movie["name"]))]

        movie_info.append(self.get_movie_description(movie))
        movie_info.append(self.get_movie_years(movie))
        movie_info.append(self.get_movie_rating(movie))
        movie_info.append(self.get_movie_countries(movie))
        movie_info.append(self.get_movie_genres(movie))
        movie_info.append(self.get_movie_length(movie))

        return movie["posterUrl"], text(*movie_info, sep="\n")
