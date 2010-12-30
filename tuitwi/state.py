#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import curses
import curses.ascii

class State(object):
    '''Stateパターン用の基底クラス'''

    def __init__(self, stdscr, form):
        self._form = form
        self._stdscr = stdscr
        self._func = {}
        self._func[curses.KEY_RESIZE] = self._resize
        self._func['default'] = self._do_nothing

    def _resize(self):
        self._form.resize(self._stdscr)
        self._form.controls['edit_line'].cur_set()
        return self

    def _do_nothing(self, ch):
        return self

    def execute(self, ch):
        if self._func.get(ch):
            return self._func[ch]()
        else:
            return self._func['default'](ch)


class ExitState(State):
    '''終了を確認する'''

    def __init__(self, stdscr, form, viewstate):
        State.__init__(self, stdscr, form)
        self._viewstate = viewstate
        self._form.controls['status_line'].text = u'ほんとに終了する? (y/n)'
        self._func[ord('y')] = self._quit
        self._func[ord('n')] = self._cancel

    def _quit(self):
        return None

    def _cancel(self):
        self._form.controls['status_line'].text = u'TuiTwi ver 0.2'
        return self._viewstate


class ConfirmDestroyMessageState(State):
    '''postの削除の確認'''

    def __init__(self, stdscr, form, viewstate):
        State.__init__(self, stdscr, form)
        self._viewstate = viewstate
        self._form.controls['status_line'].text = u'発言を削除しますか? (y/n)'
        self._func[ord('y')] = self._yes
        self._func[ord('n')] = self._no

    def _yes(self):
        i = self._form.controls['view_tab'].current_win.current_status().id
        self._viewstate.queue.put(("DestroyStatus", i))
        return self._viewstate

    def _no(self):
        self._form.controls['status_line'].text = u'TuiTwi ver 0.2'
        return self._viewstate


class SearchInputState(State):
    '''検索語句を入力する'''

    def __init__(self, stdscr, form, viewstate):
        State.__init__(self, stdscr, form)
        curses.curs_set(True)
        self._viewstate = viewstate

        self._form.controls['status_line'].text = u'検索語句を入力して下さい.無ければTABで戻れます.'
        self._form.controls['search_line'].show()
        self._form.controls['edit_line'].hide()
        self._func[curses.ascii.TAB] = self._quit
        self._func[curses.ascii.CR] = self._func[curses.ascii.LF] = self._update
        self._func['default'] = self._edit

    def _update(self):
        text = self._form.controls['search_line'].text
        self._viewstate.search_word = text
        self._form.controls['fullstatus_area'].keyword = text
        self._form.controls['search_word_line'].text = "search word: %s" % text
        curses.curs_set(False)
        return self._quit()

    def _quit(self):
        curses.curs_set(False)
        self._form.controls['status_line'].text = u'TuiTwi ver 0.2'
        self._form.controls['search_line'].hide()
        self._form.controls['edit_line'].show()
        return self._viewstate

    def _edit(self, ch):
        self._form.controls['search_line'].edit(ch)
        return self


class HelpState(State):
    '''ヘルプの表示'''

    def __init__(self, stdscr, form, viewstate):
        State.__init__(self, stdscr, form)
        self._form.controls['help_area'].show()
        self._form.controls['fullstatus_area'].hide()
        self._form.controls['view_tab'].hide()
        self._form.controls['status_line'].text = u"press 'q' to quit help."
        self._viewstate = viewstate
        self._func[ord('q')] = self._quit

    def _quit(self):
        self._form.controls['status_line'].text = u"TuiTwi ver 0.2"
        self._viewstate.resume()
        return self._viewstate


class EditState(State):
    '''発言を入力する'''

    def __init__(self, stdscr, form, viewstate):
        State.__init__(self, stdscr, form)
        curses.curs_set(True)
        self._viewstate = viewstate

        self._func[curses.ascii.TAB] = self._view
        self._func[curses.ascii.CR] = self._func[curses.ascii.LF] = self._update
        self._func['default'] = self._edit

    def _update(self):
        self._viewstate.queue.put(("PostUpdate", self._form.controls['edit_line'].text, self._viewstate.reply_id))
        self._form.controls['edit_line'].clear()
        return self._view()

    def _view(self):
        curses.curs_set(False)
        return self._viewstate

    def _edit(self, ch):
        self._form.controls['edit_line'].edit(ch)
        return self


class ViewState(State):
    '''閲覧用.'''

    def __init__(self, stdscr, form, queue, conf):
        State.__init__(self, stdscr, form)
        curses.curs_set(False)
        self._form.controls['status_line'].text = u'TuiTwi ver 0.2'
        self._form.controls['view_tab'].show()
        self._form.controls['fullstatus_area'].show()
        self._form.controls['help_area'].hide()
        self._form.controls['search_line'].hide()
        self._queue = queue
        self._command = conf.get('options').get('browser_command')
        self._search_word = ''
        self._conf = conf
        self.reply_id = None

        self._func[ord('q')] = self._quit
        self._func[ord('j')] = self._func[curses.KEY_DOWN] = self._next
        self._func[ord('k')] = self._func[curses.KEY_UP] = self._prev
        self._func[ord('g')] = self._top
        self._func[ord('G')] = self._bottom
        self._func[ord('r')] = self._update
        self._func[ord('f')] = self._fav
        self._func[ord('n')] = self._next_user_post
        self._func[ord('p')] = self._prev_user_post
        self._func[ord('P')] = self._move_to_reply_to
        self._func[ord('N')] = self._move_to_reply_from
        self._func[ord('h')] = self._func[curses.KEY_LEFT] = self._prev_tab
        self._func[ord('l')] = self._func[curses.KEY_RIGHT] = self._next_tab
        self._func[ord('o')] = self._open
        self._func[ord('H')] = self._home
        self._func[ord('R')] = self._rt
        self._func[curses.ascii.DC2] = self._official_rt
        self._func[ord('/')] = self._search_input
        self._func[ord('d')] = self._delete
        self._func[curses.ascii.SO] = self._search_next
        self._func[curses.ascii.DLE] = self._search_prev
        self._func[curses.ascii.CR] = self._func[curses.ascii.LF] = self._reply
        self._func[curses.ascii.ACK] = self._func[ord(' ')] = self._scroll_down
        self._func[curses.ascii.STX] = self._func[ord('-')] = self._scroll_up
        self._func[ord('q')] = self._quit
        self._func[curses.ascii.TAB] = self._edit
        self._func[ord('?')] = self._help

    def get_search_word(self): return self._search_word
    def set_search_word(self, val): self._search_word = val
    search_word = property(get_search_word, set_search_word)

    @property
    def queue(self): return self._queue

    def resume(self):
        self._form.controls['help_area'].hide()
        self._form.controls['view_tab'].show()
        self._form.controls['fullstatus_area'].show()

    def execute(self, ch):
        ret = State.execute(self, ch)
        self._form.controls['fullstatus_area'].status = self._form.controls['view_tab'].current_win.current_status()
        return ret

    def _delete(self):
        status = self._form.controls['view_tab'].current_win.current_status()
        if status and self._conf['credential']['user'] == status.user.screen_name:
            return ConfirmDestroyMessageState(self._stdscr, self._form, self)
        else:
            return self

    def _search_input(self):
        return SearchInputState(self._stdscr, self._form, self)

    def _search_next(self):
        self._form.controls['view_tab'].current_win.search_next_word(self._search_word)
        return self

    def _search_prev(self):
        self._form.controls['view_tab'].current_win.search_prev_word(self._search_word)
        return self

    def _open(self):
        # TODO(seikichi) URLの連結あやしい?
        status = self._form.controls['view_tab'].current_win.current_status()
        url = "http://twitter.com/%s/status/%d" % (status.user.screen_name, status.id)
        os.system(self._command % url)
        return self

    def _home(self):
        status = self._form.controls['view_tab'].current_win.current_status()
        url = "http://twitter.com/%s" % status.user.screen_name
        os.system(self._command % url)
        return self

    def _next_tab(self):
        self._form.controls['view_tab'].next_tab()
        return self

    def _prev_tab(self):
        self._form.controls['view_tab'].prev_tab()
        return self

    def _move_to_reply_from(self):
        self._form.controls['view_tab'].current_win.move_to_reply_from()
        return self

    def _move_to_reply_to(self):
        self._form.controls['view_tab'].current_win.move_to_reply_to()
        return self

    def _prev_user_post(self):
        self._form.controls['view_tab'].current_win.prev_user_post()
        return self

    def _next_user_post(self):
        self._form.controls['view_tab'].current_win.next_user_post()
        return self

    def _fav(self):
        status = self._form.controls['view_tab'].current_win.current_status()
        if not status.favorited:
            self.queue.put(("CreateFavorite", status))
        else:
            self.queue.put(("DestroyFavorite", status))
        return self

    def _reply(self):
        win = self._form.controls['view_tab'].current_win
        if win.current_status() is not None:
            self.reply_id = win.current_status().id
        self._form.controls['edit_line'].insert_string(win.reply_string())
        return EditState(self._stdscr, self._form, self)

    def _official_rt(self):
        status = self._form.controls['view_tab'].current_win.current_status()
        if status is not None:
            self._queue.put(('OfficialRT', status.id))
        return self

    def _rt(self):
        status = self._form.controls['view_tab'].current_win.current_status()
        if status is not None:
            self._form.controls['edit_line'].insert_rt(status)
        return EditState(self._stdscr, self._form, self)

    def _update(self):
        self._queue.put(('GetFriendsTimeline',))
        return self

    def _scroll_down(self):
        self._form.controls['view_tab'].current_win.scroll_down()
        return self

    def _scroll_up(self):
        self._form.controls['view_tab'].current_win.scroll_up()
        return self

    def _top(self):
        self._form.controls['view_tab'].current_win.move_to_top()
        return self

    def _bottom(self):
        self._form.controls['view_tab'].current_win.move_to_bottom()
        return self

    def _next(self):
        self._form.controls['view_tab'].current_win.next()
        return self

    def _edit(self):
        return EditState(self._stdscr, self._form, self)

    def _prev(self):
        self._form.controls['view_tab'].current_win.prev()
        return self

    def _help(self):
        return HelpState(self._stdscr, self._form, self)

    def _quit(self):
        return ExitState(self._stdscr, self._form, self)
