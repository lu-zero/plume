import os
import re
import sys
import shutil
import datetime
import subprocess
import translitcodec
from flask import Flask, render_template, Response, url_for
from flask_flatpages import FlatPages, Page, pygments_style_defs
from flask_frozen import Freezer
from flask.ext.script import Manager

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

app = Flask(__name__)
app.config.from_object(__name__)
pages = FlatPages(app)
freezer = Freezer(app)
manager = Manager(app)

datesort = lambda x,y: cmp(x['date'], y['date'])
_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')


def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        word = word.encode('translit/long')
        if word:
            result.append(word)
    return unicode(delim.join(result))


def filter_posts(path='posts/', sort=True):
    ps = [p for p in pages if path in p.path]
    if sort:
        ps.sort(cmp=datesort, reverse=True)
    return ps


def url_for_post(post):
    post_name = post.path.split('-', 3)[-1]
    return url_for('post', year=post['date'].year, month=post['date'].month,
                   day=post['date'].day, post=post_name)
app.jinja_env.globals['url_for_post'] = url_for_post
    

@app.route('/pygments.css')
def pygments_css():
    return pygments_style_defs('tango'), 200, {'Content-Type': 'text/css'}
    

@app.route('/')
def index():
    return render_template('index.html', posts=filter_posts())


@app.route('/tags/<path:tag>/')
def tag(tag):
    posts = [p for p in pages if tag in p.meta.get('tags', [])]
    posts.sort(cmp=datesort, reverse=True)
    return render_template('index.html',
        posts=posts, title=TAG_TITLE.format(tag))


@app.route('/<int:year>/')
def post_year(year):
    d = datetime.datetime(year, 1, 1)
    path ='{}/{:%Y}'.format(POST_DIR, d)
    return render_template('index.html',
        posts=filter_posts(path=path),
        title=YEAR_TITLE.format(d))


@app.route('/<int:year>/<int:month>/')
def post_year_month(year, month):
    d = datetime.datetime(year, month, 1)
    path ='{}/{:%Y-%m}'.format(POST_DIR, d)
    return render_template('index.html',
        posts=filter_posts(path=path),
        title=MONTH_YEAR_TITLE.format(d))


@app.route('/<int:year>/<int:month>/<int:day>/')
def post_year_month_day(year, month, day):
    d = datetime.datetime(year, month, day)
    path ='{}/{:%Y-%m-%d}'.format(POST_DIR, d)
    return render_template('index.html',
        posts=filter_posts(path=path),
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


# Script commands
@manager.command
def runserver():
    app.run(port=8000)

    
@manager.command
def build():
    folder = 'build'
    for file in os.listdir(folder):
        if file not in ('.git', 'CNAME', '.gitignore'):
            try:
                os.unlink(os.path.join(folder, file))
            except Exception, e:
                try:
                    shutil.rmtree(os.path.join(folder, file))
                except Exception, e:
                    pass
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
