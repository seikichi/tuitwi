#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import curses
import curses.ascii
import unicodedata
import datetime
import locale
import re
from widechartools import set_wide_chars ,get_wide_chars, adjust_n_width, split_from_width

# こんとろーる取り纏め
# あまりにもひどすぎるのであとでなんとかする
class Form(object):
    def __init__(self, stdscr, conf):
        height, width = stdscr.getmaxyx()

        # 設定の読み込み
        if conf.get('options', {}).get('ambiguous_width') == 2:
            set_wide_chars('WFA')

        self.fullstatus_height = conf.get('options', {}).get('full_status_area_height', 6)

        self._controls = {}
        self._controls['view_tab'] = TabControl(stdscr, height-self.fullstatus_height-2, width, 0, 0, conf)
        self._controls['fullstatus_area'] = FullStatusArea(stdscr, self.fullstatus_height, width, height-self.fullstatus_height-2, 0)
        self._controls['status_line'] = LabelControl(stdscr, 1, 2*(width/3), height-2, 0, attr=curses.A_REVERSE)
        self._controls['search_word_line'] = LabelControl(stdscr, 1, width-2*(width/3), height-2, 2*(width/3), attr=curses.A_REVERSE)
        self._controls['edit_line'] = EditLineControl(stdscr, height-1, attr=curses.A_NORMAL, max_text_length = 140)
        self._controls['help_area'] = LabelControl(stdscr, height-2, width, 0, 0)
        self._controls['search_line'] = EditLineControl(stdscr, height-1, attr=curses.A_NORMAL)


        self._controls['help_area'].text =  u'''\
viewモード:
 r: 更新   j/k: 上下に移動    TAB: 入力モードに移動
 RET: 選択している発言にreply                 R: RT
 h/l: タブ移動            C-f/C-b SPC/-: スクロール
 n/p: 選択している人の次/前の発言にジャンプ
 N/P: 選択している発言 に対するreply/のreply元 に移動
 ?: ヘルプ表示                 q : 終了(確認が出ます)
 G: 最新の発言にジャンプ    g: 一番古い発言にジャンプ
 o: 選択している発言を外部コマンドで開く
 H: 選択しているユーザーのページを外部コマンドで開く
 /: 検索モードに C-n/C-p: 入力した検索語句で飛ぶ
 f: ふぁぼり/ふぁぼり解除                d: 発言削除

入力モード(Emacsっぽい動きができます)
 TAB            : viewモードに戻ります
 RET            : 発言します
'''
        self.controls['search_word_line'].text = "search word: "

    def resize(self, stdscr):
        height, width = stdscr.getmaxyx()
        self._controls['view_tab'].resize(stdscr, height-self.fullstatus_height-2, width, 0, 0)
        self._controls['fullstatus_area'].resize(stdscr, self.fullstatus_height, width, height-self.fullstatus_height-2, 0)
        self._controls['status_line'].resize(stdscr, 1, 2*(width/3), height-2, 0)
        self._controls['search_word_line'].resize(stdscr, 1, width-2*(width/3), height-2, 2*(width/3))
        self._controls['edit_line'].resize(stdscr, height-1)
        self._controls['help_area'].resize(stdscr, height-2, width, 0, 0)
        self._controls['search_line'].resize(stdscr, height-1)

    def draw(self):
        for title in self._controls:
            self._controls[title].draw()
        if not self._controls['edit_line'].hidden:
            self._controls['edit_line'].cur_set()
        if not self._controls['search_line'].hidden:
            self._controls['search_line'].cur_set()

    @property
    def controls(self):
        return self._controls


class Control(object):
    def __init__(self, stdscr, nlines, ncols, begin_y, begin_x, attr=curses.A_NORMAL):
        self._create_win(stdscr, nlines, ncols, begin_y, begin_x)
        self._hidden = False
        self._attr = attr
    def resize(self, stdscr, nlines, ncols, begin_y, begin_x):
        raise Exception, 'error! please override this method!'
    def _create_win(self, stdscr, nlines, ncols, begin_y, begin_x):
        self._win = stdscr.subwin(nlines, ncols, begin_y, begin_x)
        self._height, self._width = self._win.getmaxyx()
    def draw(self):
        if self._hidden:
            return
        self._win.erase()
        self._win.bkgd(' ', self._attr)
        self._draw()
        self._win.noutrefresh()
    def _draw(self):
        raise Exception, 'error! please override this method!'
    def show(self):
        self._hidden = False
    def hide(self):
        self._hidden = True

    #プロパティ
    @property
    def hidden(self):
        return self._hidden
    @property
    def win(self):
        return self._win
    @property
    def width(self):
        return self._width
    @property
    def height(self):
        return self._height
    @property
    def attr(self):
        return self._attr

class LabelControl(Control):
    u'''ウィンドウに文字を出すだけのコントロール'''

    def __init__(self, stdscr, nlines, ncols, begin_y, begin_x, attr=curses.A_NORMAL):
        Control.__init__(self, stdscr, nlines, ncols, begin_y, begin_x, attr)
        self._text = u''

    def resize(self, stdscr, nlines, ncols, begin_y, begin_x):
        self._create_win(stdscr, nlines, ncols, begin_y, begin_x)

    def _draw(self):
        i = 0
        lines = self._text.split('\n')
        for s in reduce(lambda x, y: x+y,
                        map(lambda line: split_from_width(line, self.width-1), lines),
                        []):
            if i >= self.height:
                break
            self._win.addstr(i, 0, s)
            i += 1

    def get_text(self):
        return self._text
    def set_text(self, val):
        self._text = val
    text = property(get_text, set_text)


class FullStatusArea(Control):
    u'''アカウント名やポストを拡大表示するエリア'''
    def __init__(self, stdscr, nlines, ncols, begin_y, begin_x):
        Control.__init__(self, stdscr, nlines, ncols, begin_y, begin_x)
        self._status = None
        self._keyword = u''

    def resize(self, stdscr, nlines, ncols, begin_y, begin_x):
        self._create_win(stdscr, nlines, ncols, begin_y, begin_x)

    def get_status(self):
        return self._status
    def set_status(self, val):
        self._status = val
    status = property(get_status, set_status)

    def get_keyword(self):
        return self._keyword
    def set_keyword(self, val):
        self._keyword = val

    keyword = property(get_keyword, set_keyword)

    def _draw(self):
        if self._status is None: return
        name = (u'%s(%s)' % (self._status.user.name, self._status.user.screen_name))
        source = self._status.source
        locale.setlocale(locale.LC_ALL, 'C')
        d = datetime.datetime.strptime(self._status.created_at, u"%a %b %d %H:%M:%S +0000 %Y")
        d += datetime.timedelta(hours=9)
        time = d.strftime('%Y %b %d %a %H:%M:%S')
        locale.setlocale(locale.LC_ALL, "")
        info = (u'%s from %s' % (time, source))
        self._win.addstr(0, 0, adjust_n_width(name, self.width-1, fill=u''))

        h, i = 1, 0
        lines = self._status.text.split('\n')
        strings = reduce(lambda x, y: x+y,
                         map(lambda line: split_from_width(line, self.width-1, translate=False), lines),
                         [])
        rem = 0
        while h < self.height-1 and i < len(strings):
            self._win.move(h, 0)
            if rem:
                self._win.addstr(adjust_n_width(strings[i][:rem]), curses.A_REVERSE)

            start, end = rem, rem
            target = strings[i]
            if i != len(strings)-1:
                target += strings[i+1][:len(self._keyword)-1]

            if self._keyword:
                while target[start:].find(self._keyword) >= 0:
                    end = start+target[start:].find(self._keyword)
                    self._win.addstr(adjust_n_width(strings[i][start:end]))
                    self._win.addstr(adjust_n_width(strings[i][end:min(end+len(self._keyword),
                                                                       len(strings[i]))]),
                                     curses.A_REVERSE)
                    start = end+len(self._keyword)
            self._win.addstr(adjust_n_width(strings[i][start:]))
            if end+len(self._keyword) >= len(strings[i]):
                rem = end+len(self._keyword)-len(strings[i])
            else:
                rem = 0
            h += 1
            i += 1
        self._win.addstr(self.height-1, 0, adjust_n_width(info, self.width-1, fill=u''))

class EditLineControl(Control):
    u'''入力部分'''
    def __init__(self, stdscr, begin_y,
                 attr=curses.A_NORMAL,
                 max_text_length = sys.maxint):
        height, width = stdscr.getmaxyx()
        Control.__init__(self, stdscr, 1, width, begin_y, 0, attr)
        self._char_array = []
        self._buf = ''
        self._begin_index = 0
        self._cur_index = 0
        self._max_text_length = max_text_length
    def clear(self):
        self._buf = ''
        self._char_array = []
        self._begin_index = self._cur_index = 0
    def insert_string(self, string):
        self._home()
        for ch in string:
            self._insert(ch)
    def append_string(self, string):
        self._end()
        for ch in string:
            self._insert(ch)
    def insert_rt(self, status):
        self._end()
        for ch in u'RT @'+unicode(status.user.screen_name)+u': '+status.text:
            self._insert(ch)
        self._home()
    def _cur_x(self):
        return reduce(lambda x, y: x+y,
                      map(lambda s: s['width'],
                          self._char_array[self._begin_index:self._cur_index]),
                      0)
    def resize(self, stdscr, begin_y):
        height, width = stdscr.getmaxyx()
        self._create_win(stdscr, 1, width, begin_y, 0)
        self._cur_index = self._begin_index
    def cur_set(self):
        self._win.move(0, self._cur_x())
        self._win.noutrefresh()
    def _draw(self):
        self._win.addstr(0, 0, adjust_n_width(self.getTextFrom(self._begin_index), self._width-1))
        self.cur_set()
    def getTextFrom(self, begin):
        return u''.join(map(lambda s: s['char'], self._char_array[begin:]))
    def _insert(self, ch):
        if len(self._char_array) >= self._max_text_length:
            return
        w = 1 if get_wide_chars().find(unicodedata.east_asian_width(ch))<0 else 2
        self._char_array.insert(self._cur_index, {'char':ch, 'width':w})
        self._cur_index += 1
        while self._cur_x() > self._width-1:
            self._begin_index += 1
    def _home(self):
        self._begin_index = self._cur_index = 0
    def _end(self):
        for i in range(len(self._char_array)):
            self._right()
    def _kill_line(self):
        for i in range(len(self._char_array)):
            self._delete()
    def _left(self):
        if self._cur_index == self._begin_index:
            if self._begin_index:
                self._cur_index -= 1
                self._begin_index -= 1
        else:
            self._cur_index -= 1
    def _right(self):
        if self._cur_index > len(self._char_array)-1: return
        cur_x = self._cur_x()
        self._cur_index += 1
        while cur_x + self._char_array[self._cur_index-1]['width'] > self._width-1:
            cur_x -= self._char_array[self._begin_index]['width']
            self._begin_index += 1
    def _delete(self):
        if self._cur_index <= len(self._char_array)-1:
            self._char_array.pop(self._cur_index)
    def _backspace(self):
        if self._cur_index == self._begin_index:
            if self._begin_index:
                self._char_array.pop(self._cur_index-1)
                self._cur_index -= 1
                self._begin_index -= 1
        else:
            self._char_array.pop(self._cur_index-1)
            self._cur_index -= 1
    def edit(self, ch):
        if ch in (curses.ascii.DEL, curses.ascii.BS, curses.KEY_BACKSPACE):
            self._backspace()
        elif ch == curses.ascii.EOT:
            self._delete()
        elif ch in (curses.KEY_LEFT, curses.ascii.STX):
            self._left()
        elif ch in (curses.KEY_RIGHT, curses.ascii.ACK):
            self._right()
        elif ch in (curses.ascii.SOH, curses.KEY_HOME):
            self._home()
        elif ch in (curses.ascii.ENQ, curses.KEY_END):
            self._end()
        elif ch == curses.ascii.VT:
            self._kill_line()
        elif ch < 32 or ch > 256:
            return
        else:
            self._buf = self._buf + chr(ch)
            try:
                s = self._buf.decode(sys.stdin.encoding)
                self._buf = ''
                self._insert(s)
            except:
                pass
    @property
    def text(self):
        return u''.join(map(lambda s: s['char'], self._char_array[0:]))


class ListViewControl(Control):
    u'''リストビューっぽい何か'''

    # 割と継承前提。
    # アイテムの種類とか描画方法でみたいな
    # どうしたら賢いんだろかね

    def __init__(self, stdscr, nlines, ncols, begin_y, begin_x, conf):
        Control.__init__(self, stdscr, nlines, ncols, begin_y, begin_x)
        self._top = 0
        self._index = -1
        self._items = []
        self._on_select_change = []
        self._max_length = conf.get('options', {}).get('max_log', 200)
        self._screen_name = conf.get('credential').get('user')

    def get_max_length(self): return self._max_length
    def set_max_length(self, val): self._max_length = val
    max_length = property(get_max_length, set_max_length)

    def merge(self, new_items):
        prev_item = None
        if self._index != -1:
            prev_item = self._items[self._top+self._index]

        ret = []
        i = j = 0
        while i < len(self._items) or j < len(new_items):
            if j == len(new_items):
                ret += self._items[i:]
                break
            elif i == len(self._items):
                ret += new_items[j:]
                break
            elif self._items[i].id == new_items[j].id:
                ret.append(new_items[j])
                i += 1
                j += 1
            elif self._items[i].id > new_items[j].id:
                ret.append(new_items[j])
                j += 1
            else:
                ret.append(self._items[i])
                i += 1

        self._items = ret[-self._max_length:]

        if self._items:
            if prev_item:
                if prev_item in self._items:
                    i = self._items.index(prev_item)
                    if i < self.height:
                        self._index = i
                        self._top = 0
                    else:
                        self._top = i-self._index
                else:
                    self.move_to_top()
            else:
                self._index = self._top = 0

    def delete(self, status_id):
        for i in range(len(self._items)):
            if self._items[i].id == status_id:
                self._items.pop(i)
                if not len(self._items):
                    self._index = -1
                elif self._index+self._top >= len(self._items):
                    if self._top: self._top -= 1
                    else: self._index -= 1
                break

    def remove(self):
        self._items.pop(self._top+self._index)
        if not len(self._items):
            self._index = -1
        elif self._index+self._top >= len(self._items):
            if self._top: self._top -= 1
            else: self._index -= 1
    def add(self, status):
        self.merge([status])
    def draw(self):
        if self._index == -1: return
        for i in range(self.height):
            if i + self._top >= len(self._items):
                break
            self._draw_line(i, self._items[self._top+i])

    def _draw_line(self, index, status):
        #        raise Exception, 'please override this method!'
        current = self.current_status()

        attr = curses.A_NORMAL

        if status.id == current.id:
            # 選択している発言
            attr = curses.A_REVERSE|curses.A_BOLD
        elif status.in_reply_to_screen_name == self._screen_name:
            # 自分宛て
            attr = curses.color_pair(4)
        elif status.user.id == current.user.id:
            # 同じ人の発言
            attr = curses.color_pair(7)
        elif status.id == current.in_reply_to_status_id:
            # reply先
            attr = curses.color_pair(5)
        elif status.user.id == current.in_reply_to_user_id:
            # reply先の人
            attr = curses.color_pair(3)

        if status.favorited:
            # ふぁぼってる
            attr = attr|curses.A_UNDERLINE

        try:
            self._win.addstr(index, 0, adjust_n_width(status.user.name, 20)+' ', attr)
            self._win.addstr(adjust_n_width(status.text, self.width-22), attr)
        finally:
            pass

    def reply_string(self):
        if self._index == -1: return ''
        return u'@%s ' % self._items[self._top+self._index].user.screen_name

    # resize。バグってるので頑張って直したい
    def resize(self, stdscr, nlines, ncols, begin_y, begin_x):
        self._create_win(stdscr, nlines, ncols, begin_y, begin_x)
        if self._index >= self._height:
            self._top += self._index - self._height + 1
            self._index = self._height-1
        if self._top+self._index <= len(self._items)-1 and self._top:
            self._top = len(self._items) - self._height
            self._index = self._height-1
        if len(self._items) <= self._top + self._height < self._top + len(self._items):
            self._index = self._height - len(self._items) + self._index + self._top
            self._top = len(self._items) - self._height

    def current_status(self):
        if self._index != -1:
            return self._items[self._top+self._index]
        else: return None
    def _move(self, check, line=1):
        u'''checkがTrueを返すまでline分移動, ずっとFalseなら移動しない'''
        if self._index == -1: return
        new_index, new_top = self._index, self._top
        for i in range(len(self._items)):
            if check(self._items[new_top+new_index]):
                # checkが成功
                self._index, self._top = new_index, new_top
                return
            elif 0 <= new_index + line < min(self.height, len(self._items)):
                new_index += line
            elif (new_top + line >= 0 and
                  new_top + new_index + line<len(self._items)):
                new_top += line
    def _n_times_false(self, n):
        count = [n]
        def dispatch(status):
            if count[0]:
                count[0] -= 1
                return False
            else:
                return True
        return dispatch
    def next(self):
        self._move(self._n_times_false(1), line=1)
    def prev(self):
        self._move(self._n_times_false(1), line=-1)
    def scroll_down(self):
        self._move(self._n_times_false(self.height), line=1)
    def scroll_up(self):
        self._move(self._n_times_false(self.height), line=-1)
    def move_to_bottom(self):
        self._move(self._n_times_false(len(self._items)-1), line=1)
    def move_to_top(self):
        self._move(self._n_times_false(len(self._items)-1), line=-1)
    def move_to_reply_to(self):
        self._move(lambda status:
                   status.id == self.current_status().in_reply_to_status_id,
                   line=-1)
    def move_to_reply_from(self):
        self._move(lambda status:
                   status.in_reply_to_status_id == self.current_status().id,
                   line=1)
    def next_user_post(self):
        self._move(lambda status:
                   status.user.id == self.current_status().user.id and
                   status.id != self.current_status().id,
                   line=1)
    def prev_user_post(self):
        self._move(lambda status:
                   status.user.screen_name == self.current_status().user.screen_name and
                   status.id != self.current_status().id,
                   line=-1)
    def search_next_word(self, word):
        self._move(lambda status:
                       status.text.find(word) >= 0 and
                   status.id != self.current_status().id,
                  line = 1)
    def search_prev_word(self, word):
        self._move(lambda status:
                       status.text.find(word) >= 0 and
                   status.id != self.current_status().id,
                  line = -1)

class TabControl(Control):
    def __init__(self, stdscr, nlines, ncols, begin_y, begin_x, conf):
        Control.__init__(self, stdscr, nlines, ncols, begin_y, begin_x)
        self._wins = []
        self._tab_index = 0
        self._conf = conf
        self._tab_line = LabelControl(stdscr, 1, self.width, begin_y+nlines-1, 0, curses.A_REVERSE)

        self._conf['tabs'].append({'title':'replies', 'users':[], 'keyword':'@'+self._conf['credential']['user']})
        for tab in conf['tabs']:
            v = ListViewControl(stdscr, nlines-1, ncols, 0, 0, conf)
            self.addtab(tab['title'], v)

        for tab in self._conf['tabs']:
            tab['keyword'] = re.compile(tab['keyword'])
            tab['users'] = set(tab['users'])


    def _draw(self):
        if self._wins:
            self._wins[self._tab_index]['win'].draw()
            self._set_tab_line_text()
            self._tab_line.draw()

    def addtab(self, title, win):
        self._wins.append({'title':title, 'win':win})
    def _set_tab_line_text(self):
        ret = u''
        for i in range(len(self._wins)):
            if i == self._tab_index:
                ret += u'[' + self._wins[i]['title'] + u'] '
            else:
                ret += u' ' + self._wins[i]['title'] + u'  '
        self._tab_line.text = ret
    def next_tab(self):
        self._tab_index = (self._tab_index + 1)%len(self._wins)
    def prev_tab(self):
        self._tab_index = (self._tab_index + len(self._wins) - 1)%len(self._wins)
    def resize(self, stdscr, nlines, ncols, begin_y, begin_x):
        self._create_win(stdscr, nlines, ncols, begin_y, begin_x)
        for win in self._wins:
            win['win'].resize(stdscr, nlines-1, ncols, begin_y, begin_x)
        self._tab_line.resize(stdscr, 1, self.width, begin_y+nlines-1, 0)

    def update_timeline(self, timeline):
        for i in range(len(self._wins)):
            filtered = timeline
            if self._conf['tabs'][i]['users']:
                filtered = [status for status in filtered
                           if (status.user.screen_name in self._conf['tabs'][i]['users'])]
            filtered = [status for status in filtered
                       if self._conf['tabs'][i]['keyword'].search(status.text)]
            filtered.reverse()
            self.wins[i]['win'].merge(filtered)

    def update_replies(self, timeline):
        timeline.reverse()
        for i in range(len(self._wins)):
            if self._wins[i]['title'] == 'replies':
                self.wins[i]['win'].merge(timeline)
    def update_directmessages(self, timeline):
        pass

    @property
    def current_win(self): return self._wins[self._tab_index]['win']

    @property
    def wins(self): return self._wins
