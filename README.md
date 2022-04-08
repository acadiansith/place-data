## Using the official r/place data

To use this library, first download the 79 gzip files described in the 
[official post](https://www.reddit.com/r/place/comments/txvk2d/rplace_datasets_april_fools_2022/).

Next, run `python place_vid/place_db.py /path/to/data/dir` to build the database.
This takes about 20 minutes, and the resulting SQLite database is about 12GB.

### Making videos

![\[cc\]](https://github.com/acadiansith/place-data/blob/main/cc.gif)

Likely the most common use-case for the data will be to make time-lapse videos
of r/place.
To create a video, try something like this:

```python
from datetime import datetime
from place_vid import PlaceVideo, PlaceDB

db = PlaceDB('/path/to/place2022.db')

ts = datetime(2022, 4, 1, 10, 0)
place_video = PlaceVideo(db, 35, 148, 11, 9, ts=ts, speed='normal', scale=16, duration=26)
place_video.write_gif('cc.gif', fps=15)
```

Here the calling structure of the `PlaceVideo` constructor is
```python
    PlaceVideo(db, x, y, w, h, ts=None, speed='normal', scale=1, duration=None)
```
where
- `db` is the filename of the database file created by `place_vid/place_db.py`
- `x`, `y`, `w`, `h` define the rectangle to capture
- `ts` is the starting time, which can be a `datetime` object
- `speed` is the rate at which the timelapse should play, and can be a real number. `normal` is `1200`
- `scale` optional upscaling of the video
- `duration` length of time to capture

After instantiating the `PlaceVideo` object, you can save the video using the
[MoviePy](https://zulko.github.io/moviepy/getting_started/videoclips.html#exporting-video-clips)
interface, by calling `.write_videofile('movie.mp4', fps=24)` or even create an animated
GIF as in the above example.
