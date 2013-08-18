ImgurVacuum
===========

A ZNC module that will monitor a IRC channel, save imgur links with titles to a SQLite database and print the title to the channel.

Hard requirements
-----------

* ZNC with ModPython support
* SQLite 3 support in Python
* The PyImgur API: https://github.com/damgaard/PyImgur/
* A Imgur API key: http://api.imgur.com/

Requirements
-----------
* ZNC 1.0 (not tested on earlier versions)
* Python 3.3.2 (not tested on earlier versions)
* Some kind of Linux distribution (not tested on OS X nor Windows)

As you can see, it might work on other configurations than the ones listed above.

Setup
-----------

Right now the script only supports one channel per network. This is because I only monitor one channel in one network, so it suits me rather well.
You are welcome to submit a patch to add support for multiple channels, web admin controls etc. if you do happen to enhance it.

With that in mind, the configuration process is fairly simple. Let's start in the terminal:
```
git clone https://github.com/ToJa92/ImgurVacuum
cd ImgurVacuum
cp imgurvacuum.py <your ZNC module folder here>
```

You then need a SQLite database for storing the data.
I've choosen a table layout that works for me, but if you know Python you could obviously change it to your likings.
I used Python to create the table like this:
```
import sqlite
db_h = sqlite3.connect("/path/to/database.sqlite")
db_h.execute("CREATE TABLE imgur(ID integer primary key autoincrement, NICK text not null, LINK text not null, DATE integer not null, TITLE text)")
db_h.commit()
db_h.close()
```

The DATE column will contain a UNIX timestamp which will allow you to convert it to whatever format you desire.

In your IRC client, connect to the network where you want to monitor for Imgur links. Then:
```
/msg *status loadmod imgurvacuum
/msg *imgurvacuum help
```

And follow the instructions.
