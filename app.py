import telegram
from flask import Flask, request

from telebot.credentials import URL, bot_token
from telebot.helpers import get_shows

TOKEN = bot_token
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)


def do_welcome(chat_id, msg_id):
    bot_welcome = """
Ciao! 😎 Questo bot ti permette di scegliere velocemente il miglior film/programma che c'è stasera in tv, basandosi sui giudizi di Imdb.
Sei pronto? 🎬 si comincia!
        
Usa /top per vedere quali film/programmi sono in programmazione stasera, ordinati per rating imdb.
Oppure /programmazione per avere una lista dei programmi, ordinata per canale. 
        """
    bot.sendMessage(chat_id=chat_id, text=bot_welcome, reply_to_message_id=msg_id)


def do_best_shows(chat_id):
    shows = get_shows()
    shows.sort(key=lambda x: -x.float_rating)
    text = "\n".join([
        show.to_message()
        for show in shows
    ])
    bot.sendMessage(chat_id=chat_id, text=text, parse_mode="html")


def do_shows(chat_id):
    text = "\n".join([
        show.to_message()
        for show in get_shows()
    ])
    bot.sendMessage(chat_id=chat_id, text=text, parse_mode="html")


@app.route(f"/{TOKEN}", methods=["POST"])
def respond():
    message = telegram.Update.de_json(request.get_json(force=True), bot).effective_message
    if message is None:
        return "ok"

    chat_id = message.chat.id
    msg_id = message.message_id
    text = message.text.encode("utf-8").decode()

    # try:
    if text == "/start":
        do_welcome(chat_id, msg_id)

    elif text == "/programmazione":
        do_shows(chat_id)

    elif text == "/top":
        do_best_shows(chat_id)

    # except Exception:
    #     bot.sendMessage(chat_id=chat_id, text="😔 Mi dispiace, si è verificato un errore. Riprova più tardi.")

    return "ok"


@app.route("/set_webhook", methods=["GET", "POST"])
def set_webhook():
    s = bot.setWebhook(f"{URL}{TOKEN}")
    if s:
        return "webhook setup ok"
    else:
        return "webhook setup failed"


@app.route("/")
def index():
    return "."


if __name__ == "__main__":
    app.run(threaded=True)
