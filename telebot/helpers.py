import json
import re
from typing import Optional
from urllib import parse

import requests
from bs4 import BeautifulSoup

from telebot.credentials import OMDB_API_KEY

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


def get_imdb_id(title: str):
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


def get_rating(imdb_id: str):
    if not imdb_id:
        return None

    url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={imdb_id}"
    response = requests.get(url)
    if response.status_code != 200:
        return None

    for rating in response.json().get("Ratings", []):
        if rating["Source"] == "Internet Movie Database":
            return rating["Value"].split("/")[0].strip()


def clean_title(title):
    return re.sub(r"\(.+\)", "", title).strip()


def get_time(box):
    return _get_text_or_empty(box.find(*TIME_ARGS)).strip()


def get_genre(title):
    match = re.search(r"\((.+)\)", title)
    if match:
        return match.group(1).strip()
    return ""


def get_channel(box):
    full_text = _get_text_or_empty(box.find(*CHANNEL_ARGS))
    return full_text.strip().split("   ")[0].strip()


def get_details_page(element):
    for link in element.find_all("a"):
        if link.text.strip() == "[continua]":
            return parse.urljoin(BASE_URL, link["href"])
    return None


def get_year(url):
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


def enrich_with_rating(show, element):
    if not show.is_movie():
        return
    search_title = show.title
    details_page = get_details_page(element)
    if details_page:
        search_title += " " + get_year(details_page)

    show.imdb_id = get_imdb_id(search_title)
    show.rating = get_rating(show.imdb_id)


def _get_text_or_empty(element):
    return element.text if element else ""


def get_shows():
    shows = []
    for url in READ_URLS:
        response = requests.get(url)
        if response.status_code != 200:
            continue
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup.find_all(*BOX_ARGS):
            raw_title = _get_text_or_empty(element.find(*TITLE_ARGS))
            if not raw_title:
                continue

            show = Show(
                title=clean_title(raw_title),
                channel=get_channel(element),
                genre=get_genre(raw_title),
                time=get_time(element),
            )
            enrich_with_rating(show, element)
            shows.append(show)

    return shows
