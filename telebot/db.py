import json
import os
from datetime import datetime

import psycopg2
from flask import g


class DBHelper:
    def __init__(self):
        self._conn = None

    @classmethod
    def conn(cls):
        if "db" not in g:
            g.db = psycopg2.connect(os.environ["DATABASE_URL"])
        return g.db

    @classmethod
    def close_db(self, e=None):
        db = g.pop("db", None)

        if db is not None:
            db.close()

    @classmethod
    def init_db(self):
        c = self.conn().cursor()
        c.execute('CREATE TABLE IF NOT EXISTS show_data (show_date VARCHAR, shows TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS monitoring(day date,' + ','.join(f'req_at_{i} int' for i in range(24)) + ')')
        self.conn().commit()

        c.execute('DELETE FROM show_data where show_date < %s', (self._today(), ))
        self.conn().commit()

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
        except Exception:
            current_value = 0

        c.execute(f'INSERT INTO monitoring(day, {col_name}) VALUES (%s, %s)', (cls._today(), current_value + 1))
        cls.conn().commit()
