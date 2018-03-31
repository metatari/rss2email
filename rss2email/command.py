# Copyright (C) 2012-2014 W. Trevor King <wking@tremily.us>
#
# This file is part of rss2email.
#
# rss2email is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) version 3 of
# the License.
#
# rss2email is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# rss2email.  If not, see <http://www.gnu.org/licenses/>.

"""rss2email commands
"""

import cgi as _cgi
import cgitb as _cgitb
import os as _os
import re as _re
import sys as _sys
import xml.dom.minidom as _minidom
import xml.sax.saxutils as _saxutils

from . import LOG as _LOG
from . import error as _error


def new(feeds, args):
    "Create a new feed database."
    if args.email:
        _LOG.info('set the default target email to {}'.format(args.email))
        feeds.config['DEFAULT']['to'] = args.email
    if _os.path.exists(feeds.configfiles[-1]):
        raise _error.ConfigAlreadyExistsError(feeds=feeds)
    feeds.save()

def email(feeds, args):
    "Update the default target email address"
    if not args.email:
        _LOG.info('unset the default target email')
    else:
        _LOG.info('set the default target email to {}'.format(args.email))
    feeds.config['DEFAULT']['to'] = args.email
    feeds.save()

def add(feeds, args):
    "Add a new feed to the database"
    feed = feeds.new_feed(name=args.name, url=args.url, to=args.email)
    _LOG.info('add new feed {}'.format(feed))
    if not feed.to:
        raise _error.NoToEmailAddress(feed=feed, feeds=feeds)
    feeds.save()

def run(feeds, args):
    "Fetch feeds and send entry emails."
    if not args.index:
        args.index = range(len(feeds))
    try:
        for index in args.index:
            feed = feeds.index(index)
            if feed.active:
                try:
                    feed.run(send=args.send)
                except _error.RSS2EmailError as e:
                    e.log()
    finally:
        feeds.save()

def list(feeds, args):
    "List all the feeds in the database"
    for i,feed in enumerate(feeds):
        if feed.active:
            active_char = '*'
        else:
            active_char = ' '
        print('{}: [{}] {}'.format(i, active_char, feed))

def _set_active(feeds, args, active=True):
    "Shared by `pause` and `unpause`."
    if active:
        action = 'unpause'
    else:
        action = 'pause'
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        _LOG.info('{} feed {}'.format(action, feed))
        feed.active = active
    feeds.save()

def pause(feeds, args):
    "Pause a feed (disable fetching)"
    _set_active(feeds=feeds, args=args, active=False)

def unpause(feeds, args):
    "Unpause a feed (enable fetching)"
    _set_active(feeds=feeds, args=args, active=True)

def delete(feeds, args):
    "Remove a feed from the database"
    to_remove = []
    for index in args.index:
        feed = feeds.index(index)
        to_remove.append(feed)
    for feed in to_remove:
        _LOG.info('deleting feed {}'.format(feed))
        feeds.remove(feed)
    feeds.save()

def reset(feeds, args):
    "Forget dynamic feed data (e.g. to re-send old entries)"
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        _LOG.info('resetting feed {}'.format(feed))
        feed.reset()
    feeds.save()

def opmlimport(feeds, args):
    "Import configuration from OPML."
    if args.file:
        _LOG.info('importing feeds from {}'.format(args.file))
        f = open(args.file, 'rb')
    else:
        _LOG.info('importing feeds from stdin')
        f = _sys.stdin
    try:
        dom = _minidom.parse(f)
        new_feeds = dom.getElementsByTagName('outline')
    except Exception as e:
        raise _error.OPMLReadError() from e
    if args.file:
        f.close()
    name_slug_regexp = _re.compile('[^\w\d.-]+')
    for feed in new_feeds:
        if feed.hasAttribute('xmlUrl'):
            url = _saxutils.unescape(feed.getAttribute('xmlUrl'))
            name = None
            if feed.hasAttribute('text'):
                text = _saxutils.unescape(feed.getAttribute('text'))
                if text != url:
                    name = name_slug_regexp.sub('-', text)
            feed = feeds.new_feed(name=name, url=url)
            _LOG.info('add new feed {}'.format(feed))
    feeds.save()

def opmlexport(feeds, args):
    "Export configuration to OPML."
    if args.file:
        _LOG.info('exporting feeds to {}'.format(args.file))
        f = open(args.file, 'rb')
    else:
        _LOG.info('exporting feeds to stdout')
        f = _sys.stdout
    f.write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<opml version="1.0">\n'
        '<head>\n'
        '<title>rss2email OPML export</title>\n'
        '</head>\n'
        '<body>\n')
    for feed in feeds:
        if not feed.url:
            _LOG.debug('dropping {}'.format(feed))
            continue
        name = _saxutils.escape(feed.name)
        url = _saxutils.escape(feed.url)
        f.write('<outline type="rss" text="{}" xmlUrl="{}"/>\n'.format(
                name, url))
    f.write(
        '</body>\n'
        '</opml>\n')
    if args.file:
        f.close()

def _render_feeds(feeds):
    feed_template = '''
            <tr>
                <form method="post">
                    <td>
                        <input type="hidden"
                               name="feed-name" 
                               value="{feed.name}">
                        <input type="submit" name="action" value="Delete">
                    </td>
                    <td>{feed.name}</td>
                    <td>{feed.url}</td>
                </form>
            </tr>'''
    return ''.join(feed_template.format(feed=feed) for feed in feeds)

def cgi(feeds, args):
    "Show a config webpage when run as a CGI script."
    template = '''\
<!doctype html>
<html>
    <head>
        <title>rss2email</title>
        <style>
            table {{ border-collapse: collapse; }}
            td + td {{ border-left: 1px solid black; }}
            td input {{ width: 100%; box-sizing: border-box; }}
            th {{ border-bottom: 3px solid black; }} 
            h1 {{ text-align: center; }}
            form {{ position: absolute; }}
        </style>
    </head>
    <body>
        <h1>{user}'s rss2email configuration</h1>
        <p>{last_action}</p>
        <table>
            <tr>
                <th>Action</th>
                <th>Name</th>
                <th>URL</th>
            </tr>
            {feeds}
            <tr>
                <form method="post">
                    <td><input type="submit" name="action" value="Add"></td>
                    <td><input type="text" name="new-feed-name"></td>
                    <td><input type="url" name="new-feed-url"></td>
                </form>
            </tr>
        </table>
    </body>
</html>
'''
    if not _os.environ.get('AUTH_TYPE'):
        raise _error.NoAuthorizationError()
    if not _os.environ.get('REMOTE_USER'):
        raise _error.NoUserError()
    _cgitb.enable()
    form = _cgi.FieldStorage()
    last_action = ''
    _LOG.debug('Form: {}'.format(form))
    action = form.getfirst('action')
    try:
        if action == 'Add':
            if 'new-feed-url' not in form:
                last_action = 'Error: missing feed URL'
            else:
                feed_name = form.getfirst('new-feed-name')
                feed_url = form.getfirst('new-feed-url')
                feed = feeds.new_feed(name=feed_name, url=feed_url)
                feeds.save()
                last_action = 'Added ' + feed.name
        elif action == 'Delete':
            feed_name = form.getfirst('feed-name')
            feed = feeds[feed_name]
            feeds.remove(feed)
            feeds.save()
            last_action = 'Deleted {}'.format(feed)
        # else pass, just list the feeds
    except IndexError as err:
        last_action = 'Error: ' + str(err)
    if last_action:
        _LOG.info(last_action)
    print(template.format(user=_os.environ['REMOTE_USER'],
                          feeds=_render_feeds(feeds),
                          last_action=last_action), end='')
