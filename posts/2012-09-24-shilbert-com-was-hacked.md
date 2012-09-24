---
title: shilbert.com was hacked.
---

Over the weekend, I discovered that a lot of the pages on www.shilbert.com had some
*very* questionable content in Google's search results. As it turns out, I was
a victim of [the Pharma Hack](http://redleg-redleg.blogspot.com/2011/02/pharmacy-hack.html).
Basically, they rewrote the .htaccess file for the root of www.shilbert.com in such a way
that all pages got filled with spam for various painkillers, erectile disfunction drugs, etc. ---
*but only if the request was made by Googlebot!*
It's very sneaky because all of my PHP source files looked just fine, and I never personally saw
an issue with the site until I googled for something like "site:www.shilbert.com"
and saw that all of the pages were full of spam. Luckily, this only affected www.shilbert.com, not blog.shilbert.com as well.

I am not sure what the point of entry was.
I suspect it was either a WordPress vulnerability, a MediaWiki vulnerability, or a result of [DreamHost's shell/FTP
accounts getting hacked earlier this year](http://www.dreamhoststatus.com/2012/01/20/changing-ftpshell-passwords-due-to-security-issue/).
Since I have been backing up my site daily for years, I can see that the malicious code only
appeared a couple weeks after DreamHost was hacked --- pretty compelling evidence. 
Unfortunately I have no other evidence for this theory because the logs are long gone. Nonetheless,
I've changed all of the passwords I use on DreamHost, updated WordPress, obliterated MediaWiki, and generally
cleaned out extraneous PHP files.

One consequence of all this is that I have upgraded my offsite backup system. Previously, only
the site itself and its MySQL databases were backed up. Now, access logs are also backed up, and it emails me a list of files whose hashes have changed since yesterday, if any.
If this happens again, I will hopefully know about it sooner and
have the logs to find out how it was done.

Another consequence is that I have decided to reboot my blog. My old blog uses WordPress, which is crammed
with features, but also loads slowly, requires periodic manual upgrades
to maintain security, and generally feels heavyweight.
The new blog you are reading is entirely static HTML files, generated from Markdown text
in the manner of [jekyll](https://github.com/mojombo/jekyll).
(It's not *actually* jekyll since I am a Python guy, and it seemed simple and entertaining to write
it myself.)

I have grand designs to update this blog more frequently. My hope is that if I can muster the discipline to update
regularly, you will be able to follow the development process of my current game
more closely, and I will gain momentum by sharing the details with all of you.

Stay tuned!

--- Scott