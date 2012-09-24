import os
import jinja2
import shutil
import markdown2
import codecs
import gzip
import yaml
from datetime import datetime
import pprint

def pretty_date(when):
	month = when.strftime('%B ')
	day_year = when.strftime('%d, %Y').lstrip('0')
	return month+day_year

class Post(object):
	def __init__(self, builder, src_path):
		self.builder = builder
		basename = os.path.basename(src_path)
		non_ext, ext = os.path.splitext(basename)

		src_text = codecs.open(src_path, "r", "utf-8").read().strip()
		SPLITTER='---'
		assert src_text.startswith(SPLITTER)
		src_text = src_text[len(SPLITTER):]
		split_idx = src_text.find(SPLITTER)
		assert split_idx >= 0
		yaml_header = yaml.load(src_text[:split_idx])

		self.date = datetime(*[int(s) for s in basename.split('-')[:3]])
		self.name = non_ext
		self.title = yaml_header.get('title','')
		self.contents_markdown = src_text[split_idx+len(SPLITTER):]
		self.contents_html = markdown2.markdown(self.contents_markdown, extras=self.builder.config.get('markdown_extras'))

class PostGroup(object):
	def __init__(self, index, posts):
		self.index = index
		self.posts = posts[:]
		self.newer = None
		self.older = None
		
class Builder(object):
	def __init__(self, config_path):
		self.config = yaml.load(codecs.open('config.yml', 'r', 'utf-8'))
		
	@property
	def output_dir(self):
		return self.config['dirs']['output']
		
	def build(self):
		self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.config['dirs']['templates']),
									  autoescape=True)
		self.env.filters['pretty_date'] = pretty_date
		
		if not os.path.exists(self.output_dir):
			os.makedirs(self.output_dir)
		else:
			for f in os.listdir(self.output_dir):
				f_path = os.path.join(self.output_dir, f)
				if os.path.isfile(f_path):
					os.unlink(f_path)

		posts_dir = self.config['dirs']['posts']
		posts = []
		for f in os.listdir(posts_dir):
			post_path = os.path.join(posts_dir, f)
			if os.path.isfile(post_path) and f.endswith('.md'):
				posts.append(Post(self, post_path))
				
		posts = sorted(posts, key=lambda p:p.date, reverse=True)

		for post in posts:
			self.render_to_file(self.config['templates']['post'], post.name+'.html', {
				'post':post
			})
			
		# group posts into several per page
		curr_list = []
		curr_pg_idx = 0
		post_groups = []
		posts_per_group = int(self.config.get('posts_per_page'))
		for post in posts:
			curr_list.append(post)
			if len(curr_list) >= posts_per_group:
				post_groups.append(PostGroup(curr_pg_idx, curr_list))
				curr_list = []
				curr_pg_idx += 1
		if len(curr_list) > 0:
			post_groups.append(PostGroup(curr_pg_idx, curr_list))
		
		# link up previous/next references
		for post_group in post_groups:
			if post_group.index > 0:
				post_group.newer = post_groups[post_group.index-1]
			if post_group.index < (len(post_groups)-1):
				post_group.older = post_groups[post_group.index+1]
		
		for post_group in post_groups:
			if post_group.index == 0:
				output_name = 'index.html'
			else:
				output_name = '%d.html' % (post_group.index+1)
			self.render_to_file(self.config['templates']['post_group'], output_name, {
				'post_group':post_group
			})
		
	def render_to_file(self, template_name, output_path, template_args):
		template_args = template_args.copy()
		template_args['site'] = self.config.get('site')
		template = self.env.get_template(template_name)
		final_html_utf8 = template.render(template_args).encode('utf-8')
		with open(os.path.join(self.output_dir, output_path), 'wb') as f:
			f.write(final_html_utf8)
		if self.config.get('gzip'):
			with gzip.open(os.path.join(self.output_dir, output_path+'gz'), 'wb') as f:
				f.write(final_html_utf8)

if __name__ == '__main__':
	Builder('config.yml').build()