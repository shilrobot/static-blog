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


def make_dirs(filepath):
    """Make all the directories necessary to be able to create a path at filepath"""
    dir = os.path.dirname(filepath)
    if not os.path.exists(dir):
        os.makedirs(dir)


def split_into_groups(items, n):
    """Split a list of items into a list of groups of at most n items"""
    for i in range(0, len(items), n):
        yield items[i:i+n]


class Resource(object):
    def __init__(self, site):
        self.site = site

    def base_uri(self):
        raise NotImplementedError("Resouce.base_uri() must be implemented")

    @property
    def uri(self):
        return self.site.prefix + self.base_uri()

    @property
    def full_uri(self):
        return 'http://%s%s%s' % (self.site.config['site']['hostname'],
                                  self.site.prefix,
                                  self.base_uri())

    @property
    def output_path(self):
        # TODO: These checks probably ought to be done elsewhere
        uri = self.base_uri()
        if uri.endswith('/'):
            uri += 'index.html'
        assert uri.startswith('/')
        uri = uri[1:]
        parts = uri.split('/')
        for x in ('..', '.', ''):
            assert x not in parts, "Unwanted url segment: %s in %s (%s)" % (repr(x), parts, self.base_uri())
        return os.path.join(self.site.output_dir, *uri.split('/'))


class Post(Resource):
    def __init__(self, site, src_path):
        super(Post, self).__init__(site)
        self.older = None
        self.newer = None

        # The name of the file without directories, e.g. '2012-09-24-title.md'
        basename = os.path.basename(src_path)
        # Break the filename apart from the extension - e.g. ('2012-09-24-title', '.md')
        self.name = os.path.splitext(basename)[0]
        # Date is the year/month/day from the beginning of the filename
        self.date = datetime(*[int(s) for s in basename.split('-')[:3]])

        # Perform markdown formatting w/ metadata extraction
        extras = self.site.config.get('markdown_extras',[]) + ['metadata']
        self.contents_html = markdown2.markdown(codecs.open(src_path, "r", "utf-8").read(),
                                                extras=extras)
        self.title = self.contents_html.metadata['title']
        self.publish = (self.contents_html.metadata.get('publish','true') in ['true','yes','on'])

    def base_uri(self):
        return '/' + self.name.replace('-', '/', 3) + '/'


class PostGroup(Resource):
    def __init__(self, site, index, posts):
        super(PostGroup, self).__init__(site)
        self.index = index
        self.posts = posts[:]
        self.newer = None
        self.older = None

    def base_uri(self):
        if self.index == 0:
            return '/'
        else:
            return '/pages/%d/' % (self.index + 1)


class RSS(Resource):
    def base_uri(self):
        return '/rss.xml'


class Favicon(Resource):
    def base_uri(self):
        return '/favicon.ico'


class Site(object):
    def __init__(self, config_path):
        self.config = yaml.load(codecs.open('config.yml', 'r', 'utf-8'))
        self.output_dir = self.config['dirs']['output']
        self.prefix = self.config['site'].get('prefix')
        if not self.prefix:
            self.prefix = ''

        # Load all the posts
        posts_dir = self.config['dirs']['posts']
        self.posts = []
        for f in os.listdir(posts_dir):
            post_path = os.path.join(posts_dir, f)
            if os.path.isfile(post_path) and f.endswith('.md'):
                post = Post(self, post_path)
                if post.publish:
                    self.posts.append(post)

        # Sort posts in reverse chronological order
        self.posts.sort(key=lambda p: p.date, reverse=True)
        assert len(self.posts) > 0

        # Link up previous/next references
        for (n, post) in enumerate(self.posts):
            post.index = len(self.posts) - n - 1
            if n > 0:
                post.newer = self.posts[n - 1]
            if n < (len(self.posts) - 1):
                post.older = self.posts[n + 1]

        # Group posts into several per page
        posts_per_group = int(self.config.get('posts_per_page'))
        self.post_groups = [PostGroup(self, n, posts) 
                            for n, posts in enumerate(split_into_groups(self.posts, posts_per_group))]

        # link up previous/next references
        for post_group in self.post_groups:
            if post_group.index > 0:
                post_group.newer = self.post_groups[post_group.index - 1]
            if post_group.index < (len(self.post_groups) - 1):
                post_group.older = self.post_groups[post_group.index + 1]

        self.rss = RSS(self)
        self.favicon = Favicon(self)
        self.resources = self.posts + self.post_groups + [self.rss, self.favicon]

    def render(self):
        # Set up Jinja2 environment
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.config['dirs']['templates']),
                                      autoescape=True)
        self.env.filters['pretty_date'] = pretty_date
        self.env.filters['rfc822_date'] = rfc822_date

        # Ensure output directory exists
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir)

        for post in self.posts:
            self.render_to_file('post.html', post, {
                'post': post
            })

        for post_group in self.post_groups:
            self.render_to_file('post_group.html', post_group, {
                'post_group': post_group,
            })

        self.render_to_file('rss.xml', self.rss, {
            'rss_posts': int(self.config['rss_posts']),
        })

        if 'favicon' in self.config:
            make_dirs(self.favicon.output_path)
            shutil.copyfile(self.config['favicon'], self.favicon.output_path)

    def render_to_file(self, template_name, resource, template_args):
        output_path = resource.output_path
        print 'Render: %s -> %s' % (resource.uri, output_path)
        template_args = template_args.copy()
        template_args.update({
            'site': self.config.get('site'),
            'posts': self.posts,
            'post_groups': self.post_groups,
            'rss': self.rss,
            'home': self.post_groups[0]
        })
        template = self.env.get_template(template_name)
        final_html_utf8 = template.render(template_args).encode('utf-8')
        make_dirs(output_path)
        with open(output_path, 'wb') as f:
            f.write(final_html_utf8)
        if self.config.get('gzip'):
            # This is a bunch of BS we have to do to make a gzip archive
            # WITHOUT the original filename included in the header.
            # (It is a waste to transfer, and redbot.org doesn't seem
            # to be able to parse it, although everything else does OK.)
            # This is equivalent to the -n flag of gzip.
            sio = StringIO.StringIO()
            gzf = gzip.GzipFile(filename='', mode='w', fileobj=sio, compresslevel=9)
            gzf.write(final_html_utf8)
            gzf.flush()
            final_html_utf8_gzip = sio.getvalue()
            #print 'Compress: %s: saved %d%%' % (
            #   output_path+'.gz',
            #   100.0*(float(len(final_html_utf8) - len(final_html_utf8_gzip))/len(final_html_utf8)),
            #)
            with open(output_path + '.gz', 'wb') as f:
                f.write(final_html_utf8_gzip)


if __name__ == '__main__':
    Site('config.yml').render()
