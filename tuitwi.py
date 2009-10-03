#!/usr/bin/python
# -*- coding: utf-8 -*-

'''TUI twitter client. TuiTwi'''

__author__ = 'seikichi@kmc.gr.jp'
__version__ = '0.1'

from os import path as op
import sys
from optparse import OptionParser

if __name__ == '__main__':
    sys.path.insert(0, op.join(op.dirname(op.realpath(__file__)), 'lib'))
    import tuitwi

    parser = OptionParser(version="version %s" % __version__)
    parser.add_option('-c', '--config', dest='config',
                      help="configure file (default: ~/.tuitwirc.yml)")
    parser.add_option('-i', '--initialize',
                      action="store_true", dest='init', default=False,
                      help="Initialize config file and OAuth.")
    (options, args) = parser.parse_args()

    if not options.config:
        options.config = op.expanduser('~/.tuitwirc.yml')

    if not op.exists(options.config) or options.init:
        default = op.expanduser('tuitwirc.yml')
        tuitwi.init_config(default)

    tuitwi.start(config=options.config)
