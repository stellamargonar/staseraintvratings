import json
from datetime import datetime

import psycopg2
from flask import g

import settings


class DBHelper:
    def __init__(self):
        self._conn = None

    @classmethod
    def conn(cls):
        if "db" not in g:
            g.db = psycopg2.connect(settings.DATABASE_URL)
        return g.db

    @classmethod
    def close_db(cls, e=None):
        db = g.pop("db", None)

        if db is not None:
            db.close()

    @classmethod
    def init_db(cls):
        c = cls.conn().cursor()
        c.execute('CREATE TABLE IF NOT EXISTS show_data (show_date VARCHAR, shows TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS monitoring(day date,' + ','.join(f'req_at_{i} int' for i in range(24)) + ')')
        cls.conn().commit()

        c.execute('DELETE FROM show_data where show_date < %s', (self._today(), ))
        cls.conn().commit()

    @classmethod
    def _today(cls):
        return datetime.now().isoformat()[:10]

    @classmethod
    def get_data_from_db(cls):
        from telebot.show import ShowDecoder

        c = cls.conn().cursor()
        c.execute('SELECT shows FROM show_data WHERE show_date = %s', (cls._today(),))
        try:
            data = c.fetchone()[0]
            return json.loads(data, cls=ShowDecoder)
        except Exception:
            return None

    @classmethod
    def set_data_to_db(cls, data):
        from telebot.show import ShowEncoder

        c = cls.conn().cursor()
        c.execute('INSERT INTO show_data (show_date, shows) VALUES (%s, %s)',
                  (cls._today(), json.dumps(data, cls=ShowEncoder),))
        cls.conn().commit()

    @classmethod
    def monitor_request(cls):
        c = cls.conn().cursor()

        col_name = "req_at_{}".format(datetime.now().hour)
        c.execute(f'select {col_name} from monitoring WHERE day = %s', (cls._today(), ))

        try:
            current_value = c.fetchone()[0]
            row_exists = True
        except Exception:
            row_exists = False
            current_value = 0

        if row_exists:
            c.execute(f'UPDATE monitoring SET {col_name} = %s WHERE day = %s', (current_value + 1, cls._today()))
        else:
            c.execute(f'INSERT INTO monitoring(day, {col_name}) VALUES (%s, %s)', (cls._today(), current_value + 1))
        cls.conn().commit()
