import os
import jinja2
import shutil
import markdown2
import codecs
import gzip
import yaml
from datetime import datetime

POSTS_PATH = os.path.abspath(os.path.join(os.getcwd(), 'posts'))
OUTPUT_PATH = os.path.abspath(os.path.join(os.getcwd(), 'output'))


env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.getcwd()))
template = env.get_template('blog.html')

def process_file(post_path):
	basename = os.path.basename(post_path)
	post_date = datetime(*[int(s) for s in basename.split('-')[:3]])
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
	post_html = markdown2.markdown(markdown_body, extras=['smarty-pants'])
	
	post = {
		'html': post_html,
		'pretty_date': pretty_date(post_date),
	}
	post.update(yaml_header_parsed)
	
	final_html = template.render({
		'site': {
			'title': 'blog.shilbert.com',
		},
		'post': post,
	})
	final_html_utf8 = final_html.encode('utf-8')
	with open(os.path.join(OUTPUT_PATH, non_ext+'.html'), 'wb') as f:
		f.write(final_html_utf8)
	with gzip.open(os.path.join(OUTPUT_PATH, non_ext+'.htmlgz'), 'wb') as f:
		f.write(final_html_utf8)

def pretty_date(when):
	month = when.strftime('%B')
	day = when.strftime('%d').lstrip('0')
	#if day.endswith('1') and day != '11':
	#	suffix = 'st'
	#elif day.endswith('2') and day != '12':
	#	suffix = 'nd'
	#elif day.endswith('3') and day != '13':
	#	suffix = 'rd'
	#else:
	#	suffix = 'th'
	year = when.strftime('%Y')
	return "%s %s, %s" % (month,day,year)
				
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
		import time
		t1 = time.clock()
		process_file(post_path)
		t2 = time.clock()
		print (t2-t1*1000)
