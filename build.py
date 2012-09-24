import os
import jinja2
import shutil
import markdown2
import codecs
import gzip
import yaml

POSTS_PATH = os.path.abspath(os.path.join(os.getcwd(), 'posts'))
OUTPUT_PATH = os.path.abspath(os.path.join(os.getcwd(), 'output'))


env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.getcwd()))
template = env.get_template('blog.html')

def process_file(post_path):
	basename = os.path.basename(post_path)
	non_ext, ext = os.path.splitext(basename)
	
	src_text = codecs.open(post_path, "r", "utf-8").read().strip()
	SPLITTER='---'
	assert src_text.startswith(SPLITTER)
	src_text = src_text[len(SPLITTER):]
	split_idx = src_text.find(SPLITTER)
	assert split_idx >= 0
	yaml_header = src_text[:split_idx]
	markdown_body = src_text[split_idx+len(SPLITTER):]
	yaml_header_parsed = yaml.load(yaml_header)
	post_html = markdown2.markdown(markdown_body)
	
	post = {
		'html': post_html,
	}
	post.update(yaml_header_parsed)
	
	final_html = template.render({
		'site': {
			'title': 'blog.shilbert.com',
		},
		'post': post
	})
	final_html_utf8 = final_html.encode('utf-8')
	with open(os.path.join(OUTPUT_PATH, non_ext+'.html'), 'wb') as f:
		f.write(final_html_utf8)
	with gzip.open(os.path.join(OUTPUT_PATH, non_ext+'.htmlgz'), 'wb') as f:
		f.write(final_html_utf8)

if not os.path.exists(OUTPUT_PATH):
	os.makedirs(OUTPUT_PATH)
else:
	for f in os.listdir(OUTPUT_PATH):
		f_path = os.path.join(OUTPUT_PATH, f)
		if os.path.isfile(f_path):
			os.unlink(f_path)
		
for f in os.listdir(POSTS_PATH):
	post_path = os.path.join(POSTS_PATH, f)
	if os.path.isfile(post_path) and f.endswith('.md'):
		process_file(post_path)
