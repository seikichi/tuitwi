from setuptools import setup, find_packages
import sys, os

version = '0.3'

setup(name='tuitwi',
      version=version,
      description="TUI twitter client",
      long_description="""""",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console :: Curses',
          'Natural Language :: Japanese',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python',
          'Topic :: Communications'
          ], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='curses tui twitter',
      author='seikichi',
      author_email='seikichi@kmc.gr.jp',
      url='http://github.com/seikichi/tuitwi',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=True,
      install_requires=[
          # -*- Extra requirements: -*-
          'tweepy',
          'pyyaml',
          'simplejson'
      ],
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      tuitwi = tuitwi:main
      """,
      )
