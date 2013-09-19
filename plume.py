#!/usr/bin/env python
import os
import re
import sys
import shutil
import datetime
import subprocess
import translitcodec
from math import ceil
from urlparse import urljoin
from flask import Flask, render_template, Response, url_for, request, abort
from flask_flatpages import FlatPages, pygments_style_defs
from flask_frozen import Freezer
from flask.ext.script import Manager
from werkzeug.contrib.atom import AtomFeed

SITENAME = "Jeremy Axmacher's Writings"
AUTHOR = 'Jeremy Axmacher'
SITE_ROOT = 'http://obsoleter.com/'
DEBUG = True
FLATPAGES_AUTO_RELOAD = DEBUG
FLATPAGES_EXTENSION = '.md'
FLATPAGES_ROOT = 'content'
FREEZER_REMOVE_EXTRA_FILES = False # We do this ourselves
POST_DIR = 'posts'
PAGE_DIR = 'pages'
TAG_TITLE = 'Posts tagged <strong>{}</strong>'
YEAR_TITLE = 'Posts from the year <strong>{:%Y}</strong>'
MONTH_YEAR_TITLE = 'Posts from <strong>{:%b %Y}</strong>' 
DAY_MONTH_YEAR_TITLE = 'Posts from <strong>{:%A, %b %d, %Y}</strong>' 
EDITOR = 'gvim.exe'
PER_PAGE = 15
FREEZER_REMOVE_EXTRA_FILES = False

app = Flask(__name__)
app.config.from_object(__name__)
pages = FlatPages(app)
freezer = Freezer(app)
manager = Manager(app)

datesort = lambda x,y: cmp(x['date'], y['date'])
_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')


class Pagination(object):

    def __init__(self, page, per_page, total_count):
        self.page = page
        self.per_page = per_page
        self.total_count = total_count
        if self.page < 1 or self.page > self.pages:
            abort(404)

    def __bool__(self):
        return self.pages > 1
    __nonzero__ = __bool__

    @property
    def pages(self):
        return int(ceil(self.total_count / float(self.per_page)))

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    def slice(self, items):
        return items[(self.page - 1) * self.per_page:self.page * self.per_page]

    def iter_pages(self, left_edge=2, left_current=2, right_current=5,
                   right_edge=2):
        last = 0
        for num in xrange(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and \
                num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


def make_external(url):
    return urljoin(SITE_ROOT, url)

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        word = word.encode('translit/long')
        if word:
            result.append(word)
    return unicode(delim.join(result))


def filter_posts(path='posts/', sort=True):
    ps = [p for p in pages if path in p.path and p['published']]
    if sort:
        ps.sort(cmp=datesort, reverse=True)
    return ps


def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)
app.jinja_env.globals['url_for_other_page'] = url_for_other_page


def url_for_post(post):
    post_name = post.path.split('-', 3)[-1]
    return url_for('post', year=post['date'].year, month=post['date'].month,
                   day=post['date'].day, post=post_name)
app.jinja_env.globals['url_for_post'] = url_for_post
    

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/recent.atom')
def recent_feed():
    feed = AtomFeed('Recent Articles',
                    feed_url=request.url, url=request.url_root)
    posts = filter_posts()[:15]
    for post in posts:
        feed.add(post['title'], unicode(post.html),
                 content_type='html',
                 author=post.meta.get('author', AUTHOR),
                 url=make_external(url_for_post(post)),
                 updated=post['date'],
                 published=post['date'])
    return feed.get_response()


@app.route('/404.html')
def fourohfour():
    return render_template('404.html')


@app.route('/pygments.css')
def pygments_css():
    return pygments_style_defs('tango'), 200, {'Content-Type': 'text/css'}
    

@app.route('/', defaults={'page': 1})
@app.route('/page/<int:page>/')
def index(page):
    posts = filter_posts()
    pagination = Pagination(page, PER_PAGE, len(posts))
    posts = pagination.slice(posts)
    return render_template('index.html', posts=posts, pagination=pagination)


@app.route('/tags/<path:tag>/', defaults={'page': 1})
@app.route('/tags/<path:tag>/<int:page>/')
def tag(tag, page):
    posts = [p for p in pages if tag in p.meta.get('tags', [])]
    posts.sort(cmp=datesort, reverse=True)
    pagination = Pagination(page, PER_PAGE, len(posts))
    posts = pagination.slice(posts)
    return render_template('index.html',
        pagination=pagination,
        posts=posts, title=TAG_TITLE.format(tag))


@app.route('/<int:year>/', defaults={'page': 1})
@app.route('/<int:year>/page/<int:page>/')
def post_year(year, page):
    d = datetime.datetime(year, 1, 1)
    path ='{}/{:%Y}'.format(POST_DIR, d)
    posts = filter_posts(path=path)
    pagination = Pagination(page, PER_PAGE, len(posts))
    posts = pagination.slice(posts)
    return render_template('index.html',
        posts=posts,
        pagination=pagination,
        title=YEAR_TITLE.format(d))


@app.route('/<int:year>/<int:month>/', defaults={'page': 1})
@app.route('/<int:year>/<int:month>/page/<int:page>/')
def post_year_month(year, month, page):
    d = datetime.datetime(year, month, 1)
    path ='{}/{:%Y-%m}'.format(POST_DIR, d)
    posts = filter_posts(path=path)
    pagination = Pagination(page, PER_PAGE, len(posts))
    posts = pagination.slice(posts)
    return render_template('index.html',
        posts=posts,
        pagination=pagination,
        title=MONTH_YEAR_TITLE.format(d))


@app.route('/<int:year>/<int:month>/<int:day>/', defaults={'page': 1})
@app.route('/<int:year>/<int:month>/<int:day>/page/<int:page>/')
def post_year_month_day(year, month, day, page):
    d = datetime.datetime(year, month, day)
    path ='{}/{:%Y-%m-%d}'.format(POST_DIR, d)
    posts = filter_posts(path=path)
    pagination = Pagination(page, PER_PAGE, len(posts))
    posts = pagination.slice(posts)
    return render_template('index.html',
        posts=posts,
        pagination=pagination,
        title=DAY_MONTH_YEAR_TITLE.format(d))


@app.route('/<int:year>/<int:month>/<int:day>/<post>/')
def post(year, month, day, post):
    d = datetime.datetime(year, month, day)
    path ='posts/{:%Y-%m-%d}-{}'.format(d, post)
    post = pages.get_or_404(path)
    return render_template('post.html', post=post)


@app.route('/<name>/')
def page(name):
    path = '{}/{}'.format(PAGE_DIR, name)
    page = pages.get_or_404(path)
    return render_template('page.html', page=page)


# Freezer url generators
@freezer.register_generator
def post_year_month_day():
    posts = filter_posts()
    for year, month, day in {(p['date'].year, p['date'].month, p['date'].day)
                             for p in posts}:
        yield dict(year=year, month=month, day=day)


@freezer.register_generator
def post_year_month():
    posts = filter_posts()
    for year, month in {(p['date'].year, p['date'].month) for p in posts}:
        yield dict(year=year, month=month)


@freezer.register_generator
def post_year():
    posts = filter_posts()
    for year in {p['date'].year for p in posts}:
        yield dict(year=year)


@freezer.register_generator
def post_year():
    posts = filter_posts()
    for year in {p['date'].year for p in posts}:
        yield dict(year=year)


# Script commands
@manager.command
def runserver():
    app.run(port=8000)

    
@manager.command
def build():
    freezer.freeze()


@manager.command
def post(name):
    post_dir = os.path.join(FLATPAGES_ROOT, POST_DIR)
    if not os.path.exists(post_dir):
        os.makedirs(post_dir)
    d = datetime.datetime.today()
    date = '{:%Y-%m-%d}'.format(d)
    file_name = os.path.join(post_dir,'{}-{}.md'.format(date, slugify(name)))
    with open(file_name, 'w') as f:
        f.write('title: {}\n'.format(name.encode('utf-8')))
        f.write('date: {}\n'.format(date))
        f.write('summary: \n')
        f.write('tags: []\n')
        f.write('published: false\n')
    print 'Begin editing {}'.format(file_name)
    edit(file_name)


@manager.command
def page(name):
    page_dir = os.path.join(FLATPAGES_ROOT, PAGE_DIR)
    if not os.path.exists(page_dir):
        os.makedirs(page_dir)
    d = datetime.datetime.today()
    date = '{:%Y-%m-%d}'.format(d)
    file_name = os.path.join(page_dir, '{}.md'.format(slugify(name)))
    with open(file_name, 'w') as f:
        f.write('title: {}\n'.format(name.encode('utf-8')))
        f.write('date: {}\n'.format(date))
        f.write('summary: \n')
    print 'Begin editing {}'.format(file_name)
    edit(file_name)


def edit(file_name):
    try:
        subprocess.Popen([EDITOR, file_name])
    except OSError:
        print 'Cannot open file in editor {}.'.format(EDITOR)


if __name__ == '__main__':
    manager.run()
