import json
import os
import re
from json import JSONDecoder, JSONEncoder
from typing import Optional
from urllib import parse

import click
import requests
from bs4 import BeautifulSoup
from flask.cli import with_appcontext

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
            soup = BeautifulSoup(response.text, 'html.parser')
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
                cls._enrich_with_rating(show, element)
                shows.append(show)

        return shows

    @classmethod
    def _get_imdb_id(cls, title: str):
        if not title:
            return None

        url = f"https://sg.media-imdb.com/suggests/{title.lower()[0]}/{parse.quote(title)}.json"
        response = requests.get(url)
        if response.status_code != 200:
            return None

        try:
            data = json.loads(re.search(r"\((.+)\)", response.text).group(1))
            if data.get("d", []):
                return data["d"][0]["id"]
        except Exception:
            return None

    @classmethod
    def _get_rating(cls, imdb_id: str):
        if not imdb_id:
            return None

        url = f"http://www.omdbapi.com/?apikey={os.environ['OMDB_API_KEY']}&i={imdb_id}"
        response = requests.get(url)
        if response.status_code != 200:
            return None

        for rating in response.json().get("Ratings", []):
            if rating["Source"] == "Internet Movie Database":
                return rating["Value"].split("/")[0].strip()

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
    def _get_year(cls, url):
        response = requests.get(url)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, 'html.parser')
        details = soup.find("div", {"class": "schedatavbox"}).find_all("li")
        for item in details:
            if "Anno" not in item.text:
                continue
            return item.text.split("Anno:")[1].strip()
        return ""

    @classmethod
    def _enrich_with_rating(cls, show: Show, element):
        if not show.is_movie():
            return
        search_title = show.title
        details_page = cls._get_details_page(element)
        if details_page:
            search_title += " " + cls._get_year(details_page)

        show.imdb_id = cls._get_imdb_id(search_title)
        show.rating = cls._get_rating(show.imdb_id)

    @classmethod
    def _get_text_or_empty(cls, element):
        return element.text if element else ""


def get_today_shows():
    db_data = DBHelper.get_data_from_db()
    if db_data:
        print("DEBUG > read db data")
        return db_data
    data = ShowHelper.get_shows_from_web()
    print("DEBUG > Read from the web")
    DBHelper.set_data_to_db(data)
    return data


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    DBHelper.init_db()
    click.echo('Initialized the database.')
