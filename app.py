import os

import telegram
from flask import Flask, request

from telebot.helpers import get_today_shows, DBHelper, init_db_command

TOKEN = os.environ["BOT_TOKEN"]
bot = telegram.Bot(token=TOKEN)


def init_app(app):
    app.teardown_appcontext(DBHelper.close_db)
    app.cli.add_command(init_db_command)
    DBHelper.init_db()


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


def create_app(*args, **kwargs):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, 'staseraintvratings.sqlite'),
    )
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    init_app(app)

    @app.route(f"/{TOKEN}", methods=["POST"])
    def respond():
        message = telegram.Update.de_json(request.get_json(force=True), bot).effective_message
        if message is None:
            return "ok"

        chat_id = message.chat.id
        msg_id = message.message_id
        text = message.text.encode("utf-8").decode()

        try:
            if text == "/start":
                do_welcome(chat_id, msg_id)

            elif text == "/programmazione":
                do_shows(chat_id)

            elif text == "/top":
                do_best_shows(chat_id)

        except Exception:
            bot.sendMessage(chat_id=chat_id, text="😔 Mi dispiace, si è verificato un errore. Riprova più tardi.")

        return "ok"

    @app.route("/set_webhook", methods=["GET", "POST"])
    def set_webhook():
        s = bot.setWebhook(f"{os.environ['APP_BASE_URL']}{TOKEN}")
        if s:
            return "webhook setup ok"
        else:
            return "webhook setup failed"

    @app.route("/")
    def index():
        return "."

    return app


app = create_app()
