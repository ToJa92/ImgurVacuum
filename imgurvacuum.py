'''
ImgurVacuum - Monitors a IRC channel for imgur links, saves them and prints the title.
Copyright (C) 2014 Tobias Jansson

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see [http://www.gnu.org/licenses/].
'''
import znc
import pyimgur
import requests
import re
import sqlite3
import time
from urllib.parse import urlparse, parse_qs

class imgurvacuum(znc.Module):
    # A small function for supporting "helpers" that work the magic in the background.
    # Can take an optional string which is a specific "helper" to refresh.
    def refresh_helpers(self, specific_helper=None):
        if (specific_helper and specific_helper == "client_id") or "client_id" in self.nv:
            self.im = pyimgur.Imgur(self.nv["client_id"])
        if (specific_helper and specific_helper == "youtube_api_key") or "youtube_api_key" in self.nv:
            self.youtube_api_key = self.nv["youtube_api_key"]
        if (specific_helper and specific_helper == "sqlite_path") or "sqlite_path" in self.nv:
            self.linkdb = sqlite3.connect(self.nv["sqlite_path"])
        if (specific_helper and specific_helper == "channel") or "channel" in self.nv:
            self.channel = self.nv["channel"]

    def OnLoad(self, args, retmsg):
        # TODO: Ask user whether a database should be created or not.
        if not 'first_time' in self.nv:
            introduction_msg = '''ImgurVacuum Copyright (C) 2014 Tobias Jansson
License GPLv3: GNU GPL version 3 <http://gnu.org/licenses/gpl.html>.
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.

Looks like this is the first time you loaded this module.
To make it working, you'll need to set it up.
Send "help" to me and I'll send you instructions back.
You won't see this message again.'''
            for i in introduction_msg.splitlines(): # PutModule doesn't handle those fancy multiline strings
                self.PutModule(i)
            self.nv['first_time'] = 'false' # ZNC can only save strings
        # A regex for capturing URLs
        self.urlRegex = re.compile(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))", re.IGNORECASE | re.DOTALL)
        # URL for getting YouTube
        # The "helpers" need to be refreshed
        self.refresh_helpers()
        return True

    def OnModuleUnloading(self, mod, success, retmsg):
        self.linkdb.commit()
        self.linkdb.close()
        success.b = True
        retmsg.s = ""
        return znc.CONTINUE

    def OnModCommand(self, msg):
        for i in ["client_id", "youtube_api_key", "channel", "sqlite_path"]:
            if msg.startswith(i):
                self.nv[i] = msg.split()[1]
                self.PutModule("Updated "+i+" to: "+self.nv[i])
                self.refresh_helpers(i)
                return znc.CONTINUE

        usage_msg = '''Usage instructions.
Warning: There is no error checking done. Things can and probably will go horribly awry.
The new value will be printed, so you should be able to spot mistakes.

Commands (they take either 0 or 1 argument, argument is between ||):
client_id |<imgur client_id>| will update the Imgur client_id
youtube_api_key |<youtube api key>| will update the YouTube API key
channel |#<channel>| will update the monitored channel name. Note that # should be included.
sqlite_path |/path/to/db.sqlite| will update the path to the SQLite database.
help || will print this message again.'''
        for i in usage_msg.splitlines():
            self.PutModule(i)
        return znc.CONTINUE

    def OnChanMsg(self, nick, channel, message):
        if not ("client_id" in self.nv and
                "youtube_api_key" in self.nv and
                "channel" in self.nv and
                "sqlite_path" in self.nv):
            self.PutModule('Error: This module requires configuration. Send "help" to me and I\'ll send you instructions back.')
            return znc.CONTINUE

        # TODO: multichannel support
        # Very easy to do, but it also requires the database to be rethought
        if channel.GetName() == self.nv["channel"]:
            match = self.urlRegex.findall(message.s)
            for i in match[0]:
                # Only non-empty imgur links allowed
                if len(i) > 0 and i.find("imgur") != -1:
                    fetch = self.fetch_imgur(i)
                    if fetch["success"]:
                        fetch = fetch["response"]
                    else:
                        self.msg_channel(fetch["response"])
                        continue
                    db_entry = (nick.GetNick(), fetch.link, int(time.time()),
                                fetch.title if fetch.title else "")
                    duplicate_res = self.duplicate_imgur(db_entry)
                    if duplicate_res["duplicate"]:
                        # Duplicate link
                        duplicate_res = duplicate_res["response"]
                        if nick.GetNick() == duplicate_res[0][1]:
                            self.msg_channel("This link has already been submitted by you!")
                        else:
                            self.msg_channel("%s sent a duplicate link! OP: %s" % (db_entry[0], duplicate_res[0][1]))
                    else:
                        try:
                            self.linkdb.execute("INSERT INTO imgur VALUES (NULL, ?, ?, ?, ?)", db_entry)
                            self.linkdb.commit()
                        except sqlite3.OperationalError as e:
                            # Most likely the DB is already open
                            self.PutModule("Sqlite error: %s" % str(e))
                            self.msg_channel("An SQLite error occurred.")
                        # Only post the title if we actually have it
                        if len(db_entry[3]) > 0:
                            self.msg_channel("Imgur: %s" % db_entry[3])
                        else:
                            self.msg_channel("No Imgur title available")
                elif len(i) > 0 and i.find("youtube") != -1:
                    parsed_url = urlparse(i)
                    parsed_query_string = parse_qs(parsed_url.query)
                    # Is the "v" query parameter missing in the URL?
                    if "v" not in parsed_query_string:
                        continue
                    fetch = self.fetch_youtube(parsed_query_string["v"][0])
                    if fetch["success"]:
                        self.msg_channel("YouTube: %s"%fetch["response"].json()["items"][0]["snippet"]["title"])
                    else:
                        self.msg_channel(fetch["response"])
        return znc.CONTINUE

    def msg_channel(self, msg):
        self.PutIRC("PRIVMSG "+self.nv["channel"]+" :%s" % str(msg))

    def fetch_youtube(self, video_id):
        query_url = "https://www.googleapis.com/youtube/v3/videos?part=snippet&id=%s&key=%s" % (video_id, self.nv["youtube_api_key"])
        response = requests.get(query_url)
        if response.status_code == 200:
            return {"success": True,
                    "response": response}
        else:
            return {"success": False,
                    "response": "Error getting response from YouTube."}

    def fetch_imgur(self, url):
        try:
            resp = {"success": True,
                    "response": self.im.get_at_url(url)}
        except requests.exceptions.HTTPError: # Possibly a 404 because of a invalid link
            resp = {"success": False,
                    "response": "Error retrieving URL. Has the link 404'd?"}
        return resp

    def duplicate_imgur(self, entry):
        # Query DB to see whether the link has been posted already
        # sqlite.execute() must be provided a tuple
        res = self.linkdb.execute("SELECT * FROM imgur WHERE link=? LIMIT 1", (entry[1],)).fetchall()
        # Link has not been posted already
        return {"duplicate": len(res) > 0,
                "response": res}
