import json
import re
from json import JSONDecoder, JSONEncoder
from typing import Optional, List
from urllib import parse

import click
import requests
from bs4 import BeautifulSoup
from flask.cli import with_appcontext

import settings
from telebot.db import DBHelper

BASE_URL = "https://www.staseraintv.com/"
READ_URLS = [BASE_URL, BASE_URL + "index2.html", BASE_URL + "index3.html"]

BOX_ARGS = ("div", {"class": "singlechprevbox"})
CHANNEL_ARGS = ("div", {"class": "listingprevbox"})
TITLE_ARGS = ("span",)
TIME_ARGS = ("big",)


class Show:
    def __init__(self, title: str, genre: str,
                 channel: str,
                 time: str,
                 imdb_id: Optional[str] = None,
                 rating: Optional[str] = None, ):
        self.title = title
        self.channel = channel
        self.time = time
        self.genre = genre
        self.imdb_id = imdb_id
        self.rating = rating
        self.search_keys = []

    def is_movie(self):
        return self.genre == "Film"

    @property
    def float_rating(self):
        try:
            return float(self.rating)
        except Exception:
            return 0

    @property
    def icon(self):
        if self.genre == "Film":
            return "🎬"
        if self.genre == "Documentario":
            return "💡"
        if self.genre in {"Telefilm", "SerieTV", "Fiction", "Miniserie"}:
            return "🎥"
        if self.genre == "Reality":
            return "👤"
        if self.genre in {"Culinaria", "Cucina"}:
            return "👩‍🍳"
        if self.genre == "Sport":
            return "🥇"
        if self.genre == "Cartoni":
            return "👶"
        if self.genre in {"TalkShow", "Rubrica", "Attualita'"}:
            return "🎙"
        if self.genre == "Gioco":
            return "🎲"
        return "📺"

    def to_message(self):
        rating_str = ""
        if self.rating:
            rating_str = self.rating
            try:
                rating_str = "⭐️" * int(self.float_rating) + rating_str
            except ValueError:
                pass

        title_str = self.title
        if self.imdb_id:
            title_str = f'<a href="https://www.imdb.com/title/{self.imdb_id}">{self.title}</a>'
        return f"{self.channel} {self.time}\n" \
               + f"{self.icon} <b>{title_str}</b>" \
               + (f"\n{rating_str}\n" if rating_str else "\n")


class ShowEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Show):
            return {
                "title": o.title,
                "time": o.time,
                "genre": o.genre,
                "channel": o.channel,
                "imdb_id": o.imdb_id,
                "rating": o.rating,
            }
        return super().default(o)


class ShowDecoder(JSONDecoder):
    def decode(self, o, *args, **kwargs):
        if isinstance(o, str):
            o = super().decode(o, *args, **kwargs)
        if isinstance(o, list):
            return [self.decode(el) for el in o]
        if "title" not in o:
            return o
        return Show(**o)


class ShowHelper:
    @classmethod
    def get_shows_from_web(cls):
        shows = []
        for url in READ_URLS:
            response = requests.get(url)
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup.find_all(*BOX_ARGS):
                raw_title = cls._get_text_or_empty(element.find(*TITLE_ARGS))
                if not raw_title:
                    continue

                show = Show(
                    title=cls._clean_title(raw_title),
                    channel=cls._get_channel(element),
                    genre=cls._get_genre(raw_title),
                    time=cls._get_time(element),
                )

                if show.is_movie():
                    show.search_keys = cls._get_search_key(show, element)
                    show.imdb_id = cls._get_imdb_id(show)
                    show.rating = cls._get_rating(show)

                shows.append(show)

        return shows

    @classmethod
    def _get_rating(cls, show: Show):
        if not show.imdb_id:
            return None

        url = f"http://www.omdbapi.com/?apikey={settings.OMDB_API_KEY}&i={show.imdb_id}"
        response = requests.get(url)
        if response.status_code != 200:
            return None
        try:
            for rating in response.json().get("Ratings", []):
                if rating["Source"] == "Internet Movie Database":
                    return rating["Value"].split("/")[0].strip()
        except Exception:
            return None

    @classmethod
    def _clean_title(cls, title):
        return re.sub(r"\(.+\)", "", title).strip()

    @classmethod
    def _get_time(cls, box):
        return cls._get_text_or_empty(box.find(*TIME_ARGS)).strip()

    @classmethod
    def _get_genre(cls, title):
        match = re.search(r"\((.+)\)", title)
        if match:
            return match.group(1).strip()
        return ""

    @classmethod
    def _get_channel(cls, box):
        full_text = cls._get_text_or_empty(box.find(*CHANNEL_ARGS))
        return full_text.strip().split("   ")[0].strip()

    @classmethod
    def _get_details_page(cls, element):
        for link in element.find_all("a"):
            if link.text.strip() == "[continua]":
                return parse.urljoin(BASE_URL, link["href"])
        return None

    @classmethod
    def _get_search_key(cls, show: Show, element) -> List[str]:
        details_page_url = cls._get_details_page(element)
        if not details_page_url:
            return [show.title]

        response = requests.get(details_page_url)
        if response.status_code != 200:
            return [show.title]

        soup = BeautifulSoup(response.text, "html.parser")
        details_list = soup.find("div", {"class": "schedatavbox"}).find_all("li")

        year = None
        original_title = None
        for item in details_list:
            if "anno:" in item.text.lower():
                year = item.text.lower().split("anno:")[1].strip()
            if "titolo originale:" in item.text.lower():
                original_title = item.text.lower().split("titolo originale:")[1].strip()

        try:
            year_int = int(year)
            years = [year_int, year_int - 1, year_int + 1]
        except ValueError:
            years = [year]

        return [
            f"{show.title} {y}"
            for y in years
        ]

    @classmethod
    def _get_imdb_id(cls, show: Show) -> Optional[str]:
        for search_key in show.search_keys:
            if not search_key:
                continue

            url = f"https://sg.media-imdb.com/suggests/{search_key.lower()[0]}/{parse.quote(search_key)}.json"
            response = requests.get(url)
            if response.status_code != 200:
                continue

            try:
                data = json.loads(re.search(r"\((.+)\)", response.text).group(1))
                if data.get("d", []):
                    return data["d"][0]["id"]
            except Exception:
                continue

    @classmethod
    def _get_text_or_empty(cls, element):
        return element.text if element else ""


def get_today_shows():
    db_data = DBHelper.get_data_from_db()
    if db_data:
        return db_data
    data = ShowHelper.get_shows_from_web()
    DBHelper.set_data_to_db(data)
    return data


def refresh_today_shows():
    data = ShowHelper.get_shows_from_web()
    DBHelper.set_data_to_db(data)


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    DBHelper.init_db()
    click.echo("Initialized the database.")
