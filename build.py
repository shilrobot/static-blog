import os
import jinja2
import shutil
import markdown2
import codecs
import gzip
import yaml
from datetime import datetime

class Post(object):
	def __init__(self, src_path):
		basename = os.path.basename(post_path)
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

	@property
	def contents_html(self):
		return markdown2.markdown(self.contents_markdown, extras=['smarty-pants'])

def render_to_file(template_name, output_path, template_args):
	template = env.get_template(template_name)
	final_html_utf8 = template.render(template_args).encode('utf-8')
	with open(os.path.join(OUTPUT_DIR, output_path), 'wb') as f:
		f.write(final_html_utf8)
	if CONFIG.get('gzip'):
		with gzip.open(os.path.join(OUTPUT_DIR, output_path+'gz'), 'wb') as f:
			f.write(final_html_utf8)

def pretty_date(when):
	month = when.strftime('%B')
	day = when.strftime('%d').lstrip('0')
	year = when.strftime('%Y')
	return "%s %s, %s" % (month,day,year)

if __name__ == '__main__':
	global CONFIG, OUTPUT_DIR, env
	CONFIG = yaml.load(codecs.open('config.yml', 'r', 'utf-8'))
	#print CONFIG
	OUTPUT_DIR = CONFIG['dirs']['output']
	POSTS_DIR = CONFIG['dirs']['posts']

	env = jinja2.Environment(loader=jinja2.FileSystemLoader(CONFIG['dirs']['templates']),
							 autoescape=True)
	env.filters['pretty_date'] = pretty_date

	if not os.path.exists(OUTPUT_DIR):
		os.makedirs(OUTPUT_DIR)
	else:
		for f in os.listdir(OUTPUT_DIR):
			f_path = os.path.join(OUTPUT_DIR, f)
			if os.path.isfile(f_path):
				os.unlink(f_path)

	posts = []
	for f in os.listdir(POSTS_DIR):
		post_path = os.path.join(POSTS_DIR, f)
		if os.path.isfile(post_path) and f.endswith('.md'):
			posts.append(Post(post_path))

	for post in posts:
		render_to_file(CONFIG['templates']['post'], post.name+'.html', {
			'site': CONFIG.get('site'),
			'post':post
		})
