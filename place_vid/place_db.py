import atexit
from collections import namedtuple
import csv
from datetime import datetime, timezone
import gzip
import os
from re import I
import sqlite3
import sys

from PIL import Image, ImageColor

from tqdm import tqdm


DATA_FN_FMT = '2022_place_canvas_history-{id:012d}.csv.gzip'
MAX_DATA_FN_ID = 78
DB_FN = 'place2022.db'
WHITE_RGB = (255, 255, 255)


class PlaceDB(object):

    def __init__(self, db_fn):

        self.con = sqlite3.connect(db_fn)
        self.cur = self.con.cursor()

        self.cur.execute('SELECT min(timestamp) FROM pixels')
        self.min_ts, = self.cur.fetchone()

        self.cur.execute('SELECT max(timestamp) FROM pixels')
        self.max_ts, = self.cur.fetchone()

        atexit.register(self.cleanup)
    
    def get_frame_at(self, x, y, w, h, ts, table_name=None, base_image=None):

        if isinstance(ts, datetime):
            ts = _datetime_to_ts(ts)

        if base_image is None:
            im = Image.new('RGB', (w, h), WHITE_RGB)
        else:
            im = base_image.copy()

        for x_it in range(w):
            for y_it in range(h):
                html, _  = self.get_pixel_at(x + x_it, y + y_it, ts, table_name=table_name)
                if html is not None:
                    im.putpixel((x_it, y_it), ImageColor.getcolor(html, 'RGB'))
        
        return im

    def get_pixel_at(self, x, y, ts, table_name=None):

        if isinstance(ts, datetime):
            ts = _datetime_to_ts(ts)

        if table_name is None:
            table_name = 'pixels'
        table_name = _safe_table_name(table_name)

        self.cur.execute(f'''SELECT html, max(timestamp) 
                            FROM {table_name}
                            INNER JOIN colors ON {table_name}.color = colors.color
                            WHERE x = ? AND y = ? AND timestamp <= ?''', 
                            (x, y, ts))
        html, pixel_ts = self.cur.fetchone()

        return html, pixel_ts
    
    def create_temp_window_table(self, x, y, w, h, start_ts, end_ts, table_name=None):
        
        if table_name is None:
            table_name = 'temp_pixels'
        table_name = _safe_table_name(table_name)

        self.cur.execute(f'''CREATE TEMP TABLE {table_name} AS SELECT * FROM pixels 
                            WHERE x >= ? AND x < ? AND y >= ? AND y < ? AND timestamp > ? AND timestamp <= ?''',
                            (x, x + w, y, y + h, start_ts, end_ts))
        self.cur.execute(f'CREATE INDEX idx_{table_name}_xy_timestamp ON {table_name} (x, y, timestamp)')

        return table_name

    def cleanup(self):

        self.con.close()
    
    @classmethod
    def from_dir(cls, data_dir):

        db_fn = os.path.join(data_dir, DB_FN)

        if not os.path.exists(db_fn):
            _build_db(data_dir)
        else:
            return cls(db_fn)


def _datetime_to_ts(dt):
    return int(dt.timestamp() * 10 ** 6)


def _safe_table_name(table_name):
    return table_name.replace(';', '_')


def _build_db(data_dir):

    db_fn = os.path.join(data_dir, DB_FN)
    print(f'Building database at {db_fn}')
    con = sqlite3.connect(db_fn)

    # check for data files
    all_data_fns = [os.path.join(data_dir, DATA_FN_FMT.format(id=k)) for k in range(MAX_DATA_FN_ID + 1)]
    data_fns = [data_fn for data_fn in all_data_fns if os.path.isfile(data_fn)]
    if len(data_fns) < len(all_data_fns):
        print(f'WARNING: only have {len(data_fns)} of {len(all_data_fns)} data files')
    
    # create tables
    cur = con.cursor()
    cur.execute('CREATE TABLE pixels (timestamp INTEGER, user INTEGER, color INTEGER, x INTEGER, y INTEGER)')
    cur.execute('CREATE TABLE users (user INTEGER PRIMARY KEY, user_id TEXT)')
    cur.execute('CREATE TABLE colors (color INTEGER PRIMARY KEY, html TEXT)')

    con.commit()

    # create user and color lookups
    users = {}
    colors = {}

    print('Processing data files (this may take a while)')
    with tqdm(data_fns) as pbar:

        for data_fn in data_fns:

            # open gzip files directly
            with gzip.open(data_fn, 'rt') as f:

                # buffer large sqlite communication
                pixels_buffer = []
                users_buffer = []

                # read csv data
                csv_reader = csv.reader(f)
                for i, row in enumerate(csv_reader):

                    # skip header row
                    if i == 0:
                        continue

                    # get timestamp
                    date_str_pieces = row[0][:-4].split('.')
                    dt = datetime.fromisoformat(date_str_pieces[0]).replace(tzinfo=timezone.utc)
                    ts = _datetime_to_ts(dt)
                    if len(date_str_pieces) > 1:
                        dt_decimals = date_str_pieces[1]
                        ts += int(dt_decimals) * 10 ** (6 - len(dt_decimals))
                    
                    # get user
                    user_id = row[1]
                    if user_id not in users:
                        next_int = len(users)
                        users_buffer.append((next_int, user_id))
                        users[user_id] = next_int
                    user = users[user_id]

                    # get color
                    color_html = row[2]
                    if color_html not in colors:
                        next_int = len(colors)
                        cur.execute('INSERT INTO colors VALUES (?, ?)', (next_int, color_html))
                        colors[color_html] = next_int
                    color = colors[color_html]

                    # get x, y and add to buffer
                    xy = [int(c) for c in row[3].split(',')]
                    if len(xy) == 2:
                        x, y = xy
                        pixels_buffer.append((ts, user, color, x, y))
                    # if moderation rect, add all to buffer
                    else:
                        x1, y1, x2, y2 = xy
                        for x in range(x1, x2 + 1):
                            for y in range(y1, y2 + 1):
                                pixels_buffer.append((ts, user, color, x, y))


                    # don't send to sqlite yet

                    # occasionally send to sqlite and give progess update 
                    # (with a prime number for nice visuals)
                    if i % 15273 == 0:
                        cur.executemany('INSERT INTO pixels VALUES (?, ?, ?, ?, ?)', pixels_buffer)
                        pixels_buffer = []
                        cur.executemany('INSERT INTO users VALUES (?, ?)', users_buffer)
                        users_buffer = []
                        pbar.set_description(f'Processed {i} rows')
                
            # send remainder to sqlite 
            cur.executemany('INSERT INTO pixels VALUES (?, ?, ?, ?, ?)', pixels_buffer)
            cur.executemany('INSERT INTO users VALUES (?, ?)', users_buffer)
            con.commit()

            pbar.update(1)

    print('Creating timestamp indices')
    cur.execute('CREATE INDEX idx_pixels_timestamp ON pixels (timestamp)')
    cur.execute('CREATE INDEX idx_pixels_xy_timestamp ON pixels (x, y, timestamp)')

    print('Done building database')
    con.commit()
    con.close()


if __name__ == '__main__':

    if len(sys.argv) < 2:
        print('Running this script standalone will build the database')
        print('Usage: python place_db.py /path/to/data/dir')
    else:
        PlaceDB.from_dir(sys.argv[1])