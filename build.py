import os
import jinja2
import shutil
import markdown2
import codecs
import gzip
import yaml
from datetime import datetime
import time
import email.utils
import StringIO
import glob
import sys


def pretty_date(when):
    """Jinja2 filter to return a date like September 4, 2012"""
    month = when.strftime('%B ')
    day_year = when.strftime('%d, %Y').lstrip('0')
    return month + day_year


def rfc822_date(when):
    """Jinja2 filter to return an RFC 822 formatted date (necessary for RSS)"""
    when_tuple = when.timetuple()
    when_timestamp = time.mktime(when_tuple)
    return email.utils.formatdate(when_timestamp)


def rfc3339_date(when):
    """Jinja2 filter to return an RFC 3339 formatted date (necessary for Atom feeds)"""
    # TODO: UTC awareness?
    assert when.tzinfo is None
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_dirs(filepath):
    """Make all the directories necessary to be able to create a path at filepath"""
    dir = os.path.dirname(filepath)
    if not os.path.exists(dir):
        os.makedirs(dir)


def split_into_groups(items, n):
    """Split a list of items into a list of groups of at most n items"""
    for i in range(0, len(items), n):
        yield items[i:i + n]


def link_newer_older(items):
    """Taking a list in reverse chronological order (newest item first),
    link items to each other using the 'newer' and 'older' properties.
    The value of 'newer' is None for the first item, and 'older' is None
    for the last item."""
    for (n, item) in enumerate(items):
        item.newer = items[n - 1] if n > 0 else None
        item.older = items[n + 1] if n < (len(items) - 1) else None


def set_mtime(path, mtime):
    """Set the modification timestamp on a file"""
    if mtime is not None:
        stat = os.stat(path)
        os.utime(path, (stat.st_atime, mtime))


class Resource(object):
    def __init__(self, site):
        self.site = site

    def base_uri(self):
        raise NotImplementedError("Resouce.base_uri() must be implemented")

    def mtime(self):
        return None

    @property
    def uri(self):
        return self.site.prefix + self.base_uri()

    @property
    def full_uri(self):
        return 'http://%s%s%s' % (self.site.hostname,
                                  self.site.prefix,
                                  self.base_uri())

    @property
    def output_path(self):
        uri = self.base_uri()
        if uri.endswith('/'):
            uri += 'index.html'
        assert uri.startswith('/')
        uri = uri[1:]
        parts = uri.split('/')
        for x in ('..', '.', ''):
            assert x not in parts, "Unwanted url segment: %s in %s (%s)" % (repr(x), parts, self.base_uri())
        return os.path.join(self.site.output_dir, *uri.split('/'))

    def render_template(self, template_name, **kwargs):
        # Merge 'kwargs' and {site: self.site} into one dict
        template_args = kwargs.copy()
        template_args['site'] = self.site
        template = self.site.env.get_template(template_name)
        return template.render(template_args).encode('utf-8')


class Post(Resource):
    def __init__(self, site, src_path):
        super(Post, self).__init__(site)
        # The name of the file without directories, e.g. '2012-09-24-title.md'
        basename = os.path.basename(src_path)
        # Break the filename apart from the extension - e.g. ('2012-09-24-title', '.md')
        sans_ext = os.path.splitext(basename)[0]
        # Date is the year/month/day from the beginning of the filename.
        self.date = datetime(*[int(s) for s in sans_ext.split('-')[:3]])
        self.name = '-'.join(sans_ext.split('-')[3:])

        # Perform markdown formatting w/ metadata extraction
        extras = self.site.markdown_extras + ['metadata']
        self.contents_html = markdown2.markdown(codecs.open(src_path, "r", "utf-8").read(),
                                                extras=extras)
        self.title = self.contents_html.metadata['title']
        self.publish = (self.contents_html.metadata.get('publish', 'true') in ['true', 'yes', 'on'])

    def base_uri(self):
        return self.date.strftime('/%Y/%m/%d/') + self.name + '/'

    def render(self):
        return self.render_template('post.html', post=self)


class PostGroup(Resource):
    def __init__(self, site, index, posts):
        super(PostGroup, self).__init__(site)
        self.index = index
        self.posts = posts[:]

    def base_uri(self):
        if self.index == 0:
            return '/'
        else:
            return '/pages/%d/' % (self.index + 1)

    def render(self):
        return self.render_template('post_group.html', post_group=self)


class RSS(Resource):
    def base_uri(self):
        # Use '.rss' extension to take advantage of Apache mime.types defaults
        return '/feed.rss'

    def render(self):
        return self.render_template('rss.xml')


class Atom(Resource):
    def base_uri(self):
        # Use '.atom' extension to take advantage of Apache mime.types defaults
        return '/feed.atom'

    def render(self):
        return self.render_template('atom.xml')


class Favicon(Resource):
    def base_uri(self):
        return '/favicon.ico'

    def render(self):
        with open(self.site.favicon_path, 'rb') as f:
            return f.read()

    def mtime(self):
        return os.stat(self.site.favicon_path).st_mtime


class Site(object):
    def __init__(self, config_path):
        self.read_config(config_path)

        # Load all the posts in reverse chronological order
        self.posts = [
            Post(self, post_path)
            for post_path in glob.glob(os.path.join(self.posts_dir, '*.md'))
        ]

        # Filter out 'unpublished' posts & sort in reverse chronological order
        self.posts = sorted([p for p in self.posts if p.publish],
                            key=lambda p: p.date, reverse=True)
        assert len(self.posts) > 0

        # Link up previous/next references
        link_newer_older(self.posts)

        # Group posts into several per page
        self.post_groups = [PostGroup(self, n, posts)
                            for n, posts in enumerate(split_into_groups(self.posts, self.posts_per_page))]

        # link up previous/next references
        link_newer_older(self.post_groups)

        self.home = self.post_groups[0]
        self.resources = self.posts + self.post_groups

        if self.enable_rss:
            self.rss = RSS(self)
            self.resources.append(self.rss)
        else:
            self.rss = None

        if self.enable_atom:
            self.atom = Atom(self)
            self.resources.append(self.atom)
        else:
            self.atom = None

        if self.favicon_path is not None:
            self.favicon = Favicon(self)
            self.resources.append(self.favicon)
        else:
            self.favicon = None

    def read_config(self, config_path):
        config = yaml.load(codecs.open(config_path, 'r', 'utf-8'))
        config_dir = os.path.dirname(config_path)

        self.output_dir = os.path.join(config_dir, config['output_dir'])
        self.posts_dir = os.path.join(config_dir, config['posts_dir'])
        self.templates_dir = os.path.join(config_dir, config['templates_dir'])
        self.prefix = config.get('prefix')
        if self.prefix is None:
            self.prefix = ''
        self.feed_posts = int(config.get('feed_posts', 10))
        self.hostname = config['hostname']
        self.posts_per_page = int(config.get('posts_per_page', 10))
        self.title = config['title']
        self.description = config.get('description', '')
        self.gzip = bool(config.get('gzip', False))
        self.favicon_path = config.get('favicon')
        if self.favicon_path is not None:
            self.favicon_path = os.path.join(config_dir, self.favicon_path)
        self.enable_rss = bool(config.get('rss', True))
        self.enable_atom = bool(config.get('atom', True))
        self.markdown_extras = config.get('markdown_extras', [])
        self.author = config.get('author', {})

        self.config = config

    def render(self):
        # Set up Jinja2 environment
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.templates_dir),
                                      autoescape=True)
        self.env.filters['pretty_date'] = pretty_date
        self.env.filters['rfc822_date'] = rfc822_date
        self.env.filters['rfc3339_date'] = rfc3339_date

        # Ensure output directory exists, but clear it out.
        # Don't delete the whole directory since it is useful to just start SimpleHTTPServer
        # from that directory to serve locally.
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        else:
            for f in os.listdir(self.output_dir):
                f_path = os.path.join(self.output_dir, f)
                if os.path.isfile(f_path):
                    os.unlink(f_path)
                elif os.path.isdir(f_path):
                    shutil.rmtree(f_path)

        # Render all resources
        seen_paths = set()
        for res in self.resources:
            output_path = res.output_path
            print 'Render: %s -> %s' % (res.uri, output_path)

            # Warn about dupicates
            assert output_path not in seen_paths, ("Duplicate path: %s" % output_path)
            seen_paths.add(output_path)

            bytes = res.render()
            make_dirs(output_path)
            with open(output_path, 'wb') as f:
                f.write(bytes)
            mtime = res.mtime()
            if mtime is not None:
                set_mtime(output_path, mtime)
            if self.gzip:
                # This is a bunch of BS we have to do to make a gzip archive
                # WITHOUT the original filename included in the header.
                # (It is a waste to transfer, and redbot.org doesn't seem
                # to be able to parse it, although everything else does OK.)
                # This is equivalent to the -n flag of gzip.
                sio = StringIO.StringIO()
                with gzip.GzipFile(filename='', mode='w', fileobj=sio, compresslevel=9) as gzf:
                    gzf.write(bytes)
                gzpath = output_path + '.gz'
                with open(gzpath, 'wb') as f:
                    f.write(sio.getvalue())
                if mtime is not None:
                    set_mtime(gzpath, mtime)


if __name__ == '__main__':
    path = 'config.yml'
    if len(sys.argv) > 1:
        path = sys.argv[1]
    Site(path).render()
