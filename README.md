## Using the official r/place data

To use these scripts, first download the 79 gzip files described in the 
[official post](https://www.reddit.com/r/place/comments/txvk2d/rplace_datasets_april_fools_2022/).

Next, run `python place_vid/place_db.py /path/to/data/dir` to build the database.
This takes about 20 minutes.

Then, run `python place_vid/place_vid.py /path/to/data/dir/place2022.db` to 
extract a video. At the moment, video parameters must be specified in
the script itself, but a proper command-line interface is a priority on the TODO list.
