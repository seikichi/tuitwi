#!/usr/bin/python
# -*- coding: utf-8 -*-

from ui import *
from state import *
from updater import *
import curses
import curses.ascii
import os
import stat
import yaml
import locale
import unicodedata
import threading
import Queue
import tweepy
from os import path as op


def start(config):
    tuitwi = TuiTwi(config)
    tuitwi.run()
    return

def init_config(default_config):
    '''OAuthの認証を行い、access_tokenを取得。設定ファイルに保存する'''

    oauth_auth = tweepy.OAuthHandler(const.CONSUMER_KEY, const.CONSUMER_SECRET)

    # TODO(seikichi) ここでのエラー処理
    print 'Please authorize tuitwi: %s' % oauth_auth.get_authorization_url()
    verifier = raw_input('PIN: ').strip()

    # access_tokenの取得
    oauth_auth.get_access_token(verifier)
    access_token = oauth_auth.access_token
    key = access_token.key
    secret = access_token.secret

    # デフォルトのYAMLのロード、access_tokenの設定
    data = yaml.load(open(default_config).read().decode('utf-8'))
    data['access_token']['key'] = key
    data['access_token']['secret'] = secret
    data['credential'] = dict(user=tweepy.API(oauth_auth).me().screen_name)

    # $HOMEに書き込み
    rcfile = op.join(os.path.expanduser('~'), '.tuitwirc.yml')
    f = open(rcfile, 'w')
    yaml.dump(data, f, encoding='utf-8', allow_unicode=True, default_flow_style=False)
    os.chmod(rcfile, stat.S_IREAD|stat.S_IWRITE)
    f.close()


class TuiTwi(object):
    def __init__(self, config):
        os.chmod(config, stat.S_IREAD|stat.S_IWRITE)
        self.conf = yaml.load(open(config).read().decode('utf8'))
        self.event = threading.Event()
        self.event.clear()
        self.lock = threading.RLock()
        self.queue = Queue.Queue()

    def run(self):
        locale.setlocale(locale.LC_CTYPE, "")
        try:
            curses.wrapper(self.loop)
        except Exception, message:
            curses.nocbreak()
            curses.echo()
            curses.endwin()
            print message
        self.event.set()
        self.updater.join()
        self.twitter_communicator.join()
    def loop(self, stdscr):
        # 色の設定
        if curses.has_colors():
            curses.use_default_colors()
            curses.start_color()
            curses.init_pair(1, curses.COLOR_BLUE, -1)
            curses.init_pair(2, curses.COLOR_CYAN, -1)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            curses.init_pair(4, curses.COLOR_MAGENTA, -1)
            curses.init_pair(5, curses.COLOR_RED, -1)
            curses.init_pair(6, curses.COLOR_WHITE, -1)
            curses.init_pair(7, curses.COLOR_YELLOW, -1)

        self.form = Form(stdscr, self.conf)
        self.updater = Updater(self.queue, self.conf)
        self.twitter_communicator = TwitterCommunicator(self.queue, self.form, self.lock, self.conf)
        self.twitter_communicator.start()
        self.updater.start()

        self.state = ViewState(stdscr, self.form, self.queue, self.conf)

        self.form.draw()
        curses.doupdate()
        stdscr.nodelay(False)

        while self.state is not None:
            ch = stdscr.getch()
            self.lock.acquire()
            self.state = self.state.execute(ch)
            self.form.draw()
            curses.doupdate()
            self.lock.release()
