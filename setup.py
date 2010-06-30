from setuptools import setup, find_packages
import sys, os

version = '0.3'

setup(name='tuitwi',
      version=version,
      description="TUI twitter client",
      long_description="""\
      TUI twiter client(using curses).
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='curses tui twitter',
      author='seikichi',
      author_email='seikichi@kmc.gr.jp',
      url='http://d.hatena.ne.jp/se-kichi',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=True,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      tuitwi = tuitwi:main
      """,
      )
