from datetime import datetime, timedelta
import sys

import numpy as np
from moviepy.editor import VideoClip
from PIL import Image

from place_db import PlaceDB, _datetime_to_ts


SPEEDS = {
    'normal': 1200,
    'fast': 12000
}

class PlaceVideo(VideoClip):

    def __init__(self, db, x, y, w, h, ts=None, speed='normal', scale=1, duration=None):

        self.db = db
        self.rect = x, y, w, h

        if isinstance(ts, datetime):
            ts = _datetime_to_ts(ts)

        if ts is None:
            self.ts = self.db.min_ts
        else:
            self.ts = ts
        
        if speed in SPEEDS:
            self.speed = SPEEDS[speed]
        else:
            self.speed = float(speed)

        self.scale = scale

        super().__init__(self.make_frame, duration=duration)
    
    def make_frame(self, t=0):
        
        ts = self.ts + self.speed * t * 10 ** 6
        im = self.db.get_frame_at(*self.rect, ts)
        if self.scale != 1:
            _, _, w, h = self.rect
            im = im.resize((int(self.scale * w), int(self.scale * h)), Image.NEAREST)
        return np.asarray(im)

if __name__ == '__main__':

    ts = datetime(2022, 4, 1, 10, 0)

    if len(sys.argv) < 2:
        print('Must supply path to databse file `place2022.db`')
    
    db = PlaceDB(sys.argv[1])
    pv = PlaceVideo(db, 35, 148, 11, 9, ts=ts, speed='normal', scale=64, duration=28)
    pv.write_videofile('movie.mp4', fps=24)