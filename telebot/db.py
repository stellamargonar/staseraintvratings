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

        c.execute('DELETE FROM show_data where show_date < %s', (cls._today(), ))
        cls.conn().commit()

    @classmethod
    def _today(cls):
        return datetime.now(settings.TIMEZONE).isoformat()[:10]

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
        c.execute('DELETE FROM show_data WHERE show_date <= %s', (cls._today(), ))

        c.execute('INSERT INTO show_data (show_date, shows) VALUES (%s, %s)',
                  (cls._today(), json.dumps(data, cls=ShowEncoder),))
        cls.conn().commit()

    @classmethod
    def monitor_request(cls):
        c = cls.conn().cursor()

        col_name = "req_at_{}".format(datetime.now(settings.TIMEZONE).hour)
        c.execute(f'select COALESCE({col_name}, 0) from monitoring WHERE day = %s', (cls._today(), ))

        row = c.fetchone()
        if row is None:
            row_exists = False
            current_value = 0
        else:
            current_value = row[0]
            row_exists = True

        if row_exists:
            c.execute(f'UPDATE monitoring SET {col_name} = %s WHERE day = %s', (current_value + 1, cls._today()))
        else:
            c.execute(f'INSERT INTO monitoring(day, {col_name}) VALUES (%s, %s)', (cls._today(), current_value + 1))
        cls.conn().commit()

    @classmethod
    def _sum_all_col(cls):
        return '+'.join(f'COALESCE(req_at_{i}, 0)' for i in range(24))

    @classmethod
    def get_monitoring_report(cls) -> str:
        c = cls.conn().cursor()

        c.execute(f'SELECT {",".join(f"COALESCE(req_at_{i}, 0)" for i in range(24))} FROM monitoring WHERE day = %s', (cls._today(), ))
        row = c.fetchone()
        req_at_hour = {}
        total = 0
        if row:
            for i, val in enumerate(row):
                if val is not None and val > 0:
                    req_at_hour[i] = val
                    total += val
                else:
                    req_at_hour[i] = 0
        text = f"<b>Richieste di oggi: {total}</b>\n  "
        text += cls.time_histogram(req_at_hour)

        c.execute(f'SELECT {",".join(f"SUM(req_at_{i})" for i in range(24))} FROM monitoring')
        row = c.fetchone()
        req_at_hour = {}
        total = 0
        if row:
            for i, val in enumerate(row):
                if val is not None and val > 0:
                    req_at_hour[i] = val
                    total += val
                else:
                    req_at_hour[i] = 0
        text += f"\n\n<b>Richieste totali: {total}</b>\n  "
        text += cls.time_histogram(req_at_hour)

        return text

    @classmethod
    def time_histogram(cls, data: dict) -> str:
        max_nr = 0
        for k, v in data.items():
            if v > max_nr:
                max_nr = v

        rows = []
        for i in range(max_nr):
            row_val = max_nr - i
            row_chars = []
            for k in sorted(data.keys()):
                if data[k] <= row_val:
                    row_chars.append("  ")
                else:
                    row_chars.append("◼️ ")
            rows.append("  ".join(row_chars))
        rows.append("  ".join(str(k).zfill(2) for k in sorted(data.keys())))
        return "<pre>" + "\n".join(rows) + "</pre>"