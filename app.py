from traceback import print_exc

import telegram
from flask import Flask, request

import settings

from telebot.db import DBHelper
from telebot.show import get_today_shows, init_db_command, refresh_today_shows

bot = telegram.Bot(token=settings.TOKEN)


def init_app(app):
    app.teardown_appcontext(DBHelper.close_db)
    app.cli.add_command(init_db_command)


def do_welcome(chat_id, msg_id):
    bot_welcome = """
Ciao! 😎 Questo bot ti permette di scegliere velocemente il miglior film/programma che c'è stasera in tv, basandosi sui giudizi di Imdb.
Sei pronto? 🎬 si comincia!

Usa /top per vedere quali film/programmi sono in programmazione stasera, ordinati per rating imdb.
Oppure /programmazione per avere una lista dei programmi, ordinata per canale. 

📁 Questo bot mostra i dati di https://www.staseraintv.com combinati con le API di www.omdbapi.com.
👩‍💻 Se vuoi contribuire, il codice sorgente di questo bot lo trovi qui https://github.com/stellamargonar/staseraintvratings
        """
    bot.sendMessage(chat_id=chat_id, text=bot_welcome, reply_to_message_id=msg_id)


def do_best_shows(chat_id):
    shows = get_today_shows()
    shows.sort(key=lambda x: -x.float_rating)
    text = "\n".join([
        show.to_message()
        for show in shows
    ])
    bot.sendMessage(chat_id=chat_id, text=text, parse_mode="html")


def do_shows(chat_id):
    text = "\n".join([
        show.to_message()
        for show in get_today_shows()
    ])
    bot.sendMessage(chat_id=chat_id, text=text, parse_mode="html")


def do_top_n(chat_id, n):
    shows = get_today_shows()
    shows.sort(key=lambda x: -x.float_rating)
    text = "\n".join([
        show.to_message()
        for show in shows
        if show.is_movie()
    ][:n])
    bot.sendMessage(chat_id=chat_id, text=text, parse_mode="html")


def do_report_monitoring(chat_id):
    bot.sendMessage(chat_id=chat_id, text=DBHelper.get_monitoring_report(), parse_mode="html")


def create_app(*args, **kwargs):
    app = Flask(__name__, instance_relative_config=True)
    init_app(app)

    @app.route(f"/{settings.TOKEN}", methods=["POST"])
    def respond():
        message = telegram.Update.de_json(request.get_json(force=True), bot).effective_message
        if message is None:
            return "ok"

        chat_id = message.chat.id
        msg_id = message.message_id
        text = message.text.encode("utf-8").decode()

        do_monitoring = True
        try:
            if text == "/start":
                do_welcome(chat_id, msg_id)

            elif text == "/programmazione" or text == "/list":
                do_shows(chat_id)

            elif text == "/top":
                do_best_shows(chat_id)

            elif text == "/top5":
                do_top_n(chat_id, 5)

            elif text == "/top3":
                do_top_n(chat_id, 3)

            elif text == f"/refresh {settings.ADMIN_SECRET}":
                refresh_today_shows()
                do_monitoring = False

            elif text == f"/report {settings.ADMIN_SECRET}":
                do_report_monitoring(chat_id)
                do_monitoring = False

        except Exception:
            bot.sendMessage(chat_id=chat_id, text="😔 Mi dispiace, si è verificato un errore. Riprova più tardi.")
            print_exc()

        if do_monitoring:
            try:
                DBHelper.monitor_request()
            except Exception:
                print_exc()

        return "ok"

    @app.route("/set_webhook", methods=["GET", "POST"])
    def set_webhook():
        s = bot.setWebhook(f"{settings.APP_BASE_URL}{settings.TOKEN}")
        if s:
            return "webhook setup ok"
        else:
            return "webhook setup failed"

    @app.route("/")
    def index():
        return "."

    return app


app = create_app()
