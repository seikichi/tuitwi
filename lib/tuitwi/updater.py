#!/usr/bin/python
# -*- coding: utf-8 -*-

import curses
import tweepy
import tweepy.parsers
import threading
import string
import re
import locale
import const

# 更新処理のスレッドと、一定の間隔でそれに更新を命じるスレッド
# queueへ入れる命令形式は
#  更新: ('GetFriendsTimeline',)
#  投稿: ('PostUpdate', text, reply_id)
# のように, [0]がpython-twitterのメソッド名
# 以降がargs (ただしUpdate系のsince_idはこちらが持つ)
# 例外としては ('Quit',) これは終了を指示する


class Updater(threading.Thread):
    ''' 一定の間隔でジョブキューに更新処理を入れる '''

    def __init__(self, queue, conf):
        self._queue = queue
        self._stopevent = threading.Event()
        self._sleepperiod = conf.get('options', {}).get('update_interval', 60)
        self._dm_reply_interval = conf.get('options', {}).get('reply_check_interval', 20)
        self._count = self._dm_reply_interval
        threading.Thread.__init__(self)

    def run(self):
        '''メインループ'''
        while not self._stopevent.isSet():
            # 更新処理を投げる
            self._queue.put(("GetFriendsTimeline",))
            self._count += 1

            if self._count >= self._dm_reply_interval:
                # 一定の間隔を越えれば、DMとreplyの更新を投げる
                self._count = 0
#                self._queue.put(("GetDirectMessages",))
                self._queue.put(("GetReplies",))

            self._stopevent.wait(self._sleepperiod)

    def join(self, timeout=None):
        '''スレッドを停止して終了を待つ'''
        self._stopevent.set()
        threading.Thread.join(self, timeout)


class TwitterCommunicator(threading.Thread):
    '''ジョブキューをもとに、更新処理などを行なう.'''

    def __init__(self, queue, form, lock, conf):
        self._queue = queue
        self._form = form
        self._lock = lock
        self._conf = conf

        self._stopevent = threading.Event()
        self._since_id = 0
        self._rpl_since_id = 0
        self._dm_since_id = 0
        tkn = tweepy.oauth.OAuthToken(self._conf['access_token']['key'],
                                      self._conf['access_token']['secret'])
        oauth_auth = tweepy.OAuthHandler(const.CONSUMER_KEY, const.CONSUMER_SECRET)
        oauth_auth.access_token = tkn
        self._api = tweepy.API(oauth_auth)

        # tweepyの中でdatetime.strptimeが呼ばれているため、
        # そこの部分の関数を無理矢理変える
        # そうしないとロケールの問題で落ちる;;
        tweepy.parsers._parse_datetime = lambda s: s
        tweepy.parsers._parse_search_datetime = lambda s: s

        self._funcs = {}
        self._funcs['GetFriendsTimeline'] = self._GetFriendsTimeline
        self._funcs['GetDirectMessages'] = self._GetDirectMessages
        self._funcs['GetReplies'] = self._GetReplies
        self._funcs['PostUpdate'] = self._PostUpdate
        self._funcs['DestroyStatus'] = self._DestroyStatus
        self._funcs['CreateFavorite'] = self._CreateFavorite
        self._funcs['DestroyFavorite'] = self._DestroyFavorite
        self._funcs['Quit'] = self._Quit
        threading.Thread.__init__(self)


    def run(self):
        while not self._stopevent.isSet():
            job = self._queue.get()
            self._funcs[job[0]](job[1:])

    def join(self, timeout=None):
        '''スレッドを停止して終了を待つ'''
        self._stopevent.set()

        # stopeventをsetした場合、あとは一回でもgetが呼ばれれば、
        # その後終了する。queueが空の場合のため、空の命令を送っておく
        self._queue.put(("Quit",))

        threading.Thread.join(self, timeout)

    def _translateTimeline(self, timeline):
        '''改行を空白に変更したり、CP932とかの問題を解決する'''
        def translate(text):
            text = re.sub(u'('+u'|'.join(string.whitespace)+u')',
                          u' ',
                          text)
            text = text.replace(u'&lt;', u'<')
            text = text.replace(u'&gt;', u'>')
            text = text.replace(u'\u2015', u'\u2014')
            text = text.replace(u'\uff5e', u'\u301c')
            text = text.replace(u'\uff0d', u'\u2212')
            text = text.replace(u'\u2225', u'\u2016')
            text = text.replace(u'\uffe2', u'\u00ac')
            text = text.replace(u'\uffe1', u'\u00a3')
            text = text.replace(u'\uffe0', u'\u00a2')
            return text

        for status in timeline:
            status.text = translate(status.text)
            status.user.name = translate(status.user.name)

    # 以下更新系関数
    # 流れとしては 1.tryの中で更新 2.ロック取得, tryの中で更新 3.ロックの開放
    def _GetFriendsTimeline(self, args):
        '''TLを取得する'''
        try:
            if self._since_id:
                timeline = self._api.friends_timeline(since_id = self._since_id)
            else:
                timeline = self._api.friends_timeline(count=200)
            msg = u'TLの取得に成功しました'
        except Exception, e:
            msg = u'TLの取得に失敗しました'
            timeline = []

        self._translateTimeline(timeline)

        self._lock.acquire()
        try:
            if timeline:
                self._form.controls['view_tab'].update_timeline(timeline)
                self._since_id = timeline[0].id
            self._form.controls['status_line'].text = msg
            self._form.draw()
            curses.doupdate()
        finally:
            self._lock.release()

    def _GetReplies(self, args):
        '''Replyを取得する'''
        try:
            if self._rpl_since_id:
                timeline = self._api.mentions(since_id=self._rpl_since_id)
            else:
                timeline = self._api.mentions()
            msg = u'Replyの取得に成功しました'
        except Exception, e:
            msg = u'Replyの取得に失敗しました'
            timeline = []

        self._translateTimeline(timeline)

        self._lock.acquire()
        try:
            if timeline:
                self._form.controls['view_tab'].update_replies(timeline)
                self._rpl_since_id = timeline[0].id
            self._form.controls['status_line'].text = msg
            self._form.draw()
            curses.doupdate()
        finally:
            self._lock.release()


    def _GetDirectMessages(self, args):
        '''DMを取得する'''
        try:
            if self._dm_since_id:
                timeline = self._api.direct_messages(since_id=self._dm_since_id)
            else:
                timeline = self._api.direct_messages()
            msg = u'DMの取得に成功しました'
        except Exception, e:
            msg = u'DMの取得に失敗しました'
            timeline = []

        self._translateTimeline(timeline)

        self._lock.acquire()
        try:
            if timeline:
                self._form.controls['view_tab'].update_directmessages(timeline)
                self._dm_since_id = timeline[0].id
            self._form.controls['status_line'].text = msg
            self._form.draw()
            curses.doupdate()
        finally:
            self._lock.release()


    def _PostUpdate(self, args):
        '''発言する'''
        text = args[0]
        reply_id = args[1]
        try:
            status = self._api.update_status(text.encode('utf-8'), reply_id)
            msg = u'Postに成功しました'
        except Exception, e:
            status = None
            msg = u'Postに失敗しました'

        self._lock.acquire()
        try:
            if status is not None:
                timeline = [status]
                self._translateTimeline(timeline)
                self._form.controls['view_tab'].update_timeline(timeline)
            self._form.controls['status_line'].text = msg
            self._form.draw()
            curses.doupdate()
        finally:
            self._lock.release()



    def _CreateFavorite(self, args):
        status = args[0]
        try:
            st = self._api.create_favorite(status.id)
            msg = u'favに成功しました'
        except Exception, e:
            st = None
            msg = u'favに失敗しました'

        self._lock.acquire()
        try:
            if st is not None:
                status.favorited = True
            self._form.controls['status_line'].text = msg
            self._form.draw()
            curses.doupdate()
        finally:
            self._lock.release()


    def _DestroyFavorite(self, args):
        status = args[0]
        try:
            st = self._api.destroy_favorite(status.id)
            msg = u'fav削除に成功しました'
        except Exception, e:
            st = None
            msg = u'fav削除に失敗しました'

        self._lock.acquire()
        try:
            if st is not None:
                status.favorited = False
            self._form.controls['status_line'].text = msg
            self._form.draw()
            curses.doupdate()
        finally:
            self._lock.release()


    def _DestroyStatus(self, args):
        '''削除する'''
        deleted = False
        try:
            self._api.destroy_status(args[0])
            msg = u'削除に成功しました'
            deleted = True
        except Exception, e:
            msg = u'削除に失敗しました'

        self._lock.acquire()
        try:
            if deleted:
                for win in self._form.controls['view_tab'].wins:
                    win['win'].delete(args[0])
            self._form.controls['status_line'].text = msg
            self._form.draw()
            curses.doupdate()
        finally:
            self._lock.release()


    def _Quit(self, arg):
        pass

