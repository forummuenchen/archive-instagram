# Low-tech Instagram archive

This repository contains scripts to collect Instagram profiles and posts and then renders HTML websites to inspect them. 

The goal is medium and long term archiving. As  Alex Chan wrote in [Using static websites for tiny archives](https://alexwlchan.net/2024/static-websites/):

> HTML is low maintenance, it’s flexible, and it’s not going anywhere. It’s the foundation of the entire web, and pretty much every modern computer has a web browser that can render HTML pages. These files will be usable for a very long time – probably decades, if not more.

## Prerequisites

This projects uses [uv](https://github.com/astral-sh/uv) package manager. 

First, install `uv`: 

```bash
# install with pip
pip install uv
# or curl (Linux/macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or PowerShell (Windows)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Create a virtual environment
uv venv
# Activate the virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

Not using `uv`? There is also a `requirements.txt`.


## Step 1: Download Instagram posts and profiles

Getting data out of Meta plattforms is not easy. There is no such thing as an API and Meta tries to prevent scraping. But of course, there are people building and maintaining software to download images, videos or texts. On of the most sophisticated tools is [instaloader](https://instaloader.github.io/).


### Prepare an Instagram account

First, you need an Instagram account, either one you are already having or a new one just for scraping purposes. 
Beware to do some interactions - like an image, write a comment, upload a profile image and some nonesense posts. 
Instagram will be suspicous very soon, but the downloading works nonetheless. 

### Save and import cookies and sessions

Assuming you are logged in to Instagram in a browser, run the script `01-get-instagram-posts/00-import-brower-session.py`. 

```bash
uv run 01-get-instagram-posts/00-import-brower-session.py
```

It's copied from the [instaloader's troubleshooting page](https://instaloader.github.io/troubleshooting.html#login-error ) and makes sure the login works. 

### Start downloading

Creata `data` directory and start fetching the data ... The folder structure is defined in the command and should not be changed in order to maintain compatibility.

Example command to get data for one Instagram account:

```bash
instaloader forummuenchenev --stories --highlights --tagged --reels --comments --no-compress-json --max-connection-attempts 10 --dirname-pattern=data/{target} --filename-pattern={date_utc:%Y}/{shortcode}_{date_utc}_UTC  --sanitize-paths --login INSTA_ACCOUNT
```


Example command to get data for multiple Instagram accounts:

```bash
instaloader forummuenchenev lez_lesbischqueereszentrum --stories --highlights --tagged --reels --comments --no-compress-json --max-connection-attempts 10 --dirname-pattern=data/{target} --filename-pattern={date_utc:%Y}/{shortcode}_{date_utc}_UTC  --sanitize-paths --login INSTA_ACCOUNT
```

Example for multiple Instagram accounts, stored in a list `01-get-instagram-posts/accounts.txt`.
This uses instaloaders [`args` parameters](https://instaloader.github.io/cli-options.html#cmdoption-arg-args.txt).

```bash
instaloader --stories --highlights --tagged --reels --comments --max-connection-attempts 10 --dirname-pattern=data/{target} --filename-pattern={date_utc:%Y}/{shortcode}_{date_utc}_UTC  --sanitize-paths --login +01-get-instagram-posts/insta_account.txt +01-get-instagram-posts/accounts.txt
```

## Step 2: Build static HTML websites

After getting the data, it is used to build static HTML websites. It builds [upon pincusion](https://github.com/Historypin/pincushion).

![](static/img/screenshot-year-posts.png)

```bash
uv run 02-build-pages/build-html.py
```

## Links

[Using static websites for tiny archives](https://alexwlchan.net/2024/static-websites/)

[pincushion](https://inkdroid.org/2024/10/20/pincushion/)

https://instaloader.github.io/cli-options.html#which-posts-to-download
https://github.com/AdriaPadilla/InstaloaderScripts/tree/master/Instaloader_scripts/get_profile_posts

## Known Issues

- When the profiles does not show the likes count, we get `-1`: https://github.com/instaloader/instaloader/issues/1314