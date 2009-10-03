#!/usr/bin/python
# -*- coding: utf-8 -*-

# Unicodeの曖昧な幅の文字などを扱う時の関数群
# 基本的にInputはunicode/ascii
# Outputはcursesに直接入れれる形にしている(変更するかも)

import sys
import unicodedata

# 幅2として扱う文字の集合
# 行儀が悪いのでどうにかする(TODO:seikichi)
WIDE_CHARS = ['WF']

def get_wide_chars():
    return WIDE_CHARS[0]

def set_wide_chars(val):
    WIDE_CHARS[0] = val

def adjust_n_width(s, width=0, fill=u' ', translate=True):
    u'''
    背景色設定用(bkgdで指定するとズレる)
    幅をnになるよう調整する
    長ければ切り詰め、短ければfillで詰める
    '''
    if not isinstance(s, unicode): s = unicode(s)
    if width <= 0: return s.encode(sys.stdout.encoding)
    u, i, diff = u'', 0, 0
    for c in s:
        diff = 1 if WIDE_CHARS[0].find(unicodedata.east_asian_width(c))<0 else 2
        if i+diff > width: break
        u += c
        i += diff
    u += fill*(width-i)
    if translate:
        u = u.encode(sys.stdout.encoding)
    return u


def split_from_width(s, max_width, translate=True):
    u'''
    表示幅に従ってmax_width以内ずつにsをsplitする.
    '''
    if not isinstance(s, unicode):
        s = unicode(s)
    ret = []
    length, diff = 0, 0
    tmp = u''
    for c in s:
        diff = 1 if WIDE_CHARS[0].find(unicodedata.east_asian_width(c))<0 else 2
        if length + diff > max_width:
            ret.append(tmp)
            length = diff
            tmp = c
        else:
            tmp += c
            length += diff
    if tmp:
        ret.append(tmp)
    if translate:
        ret = map(lambda s: s.encode(sys.stdout.encoding), ret)
    return ret
