# Low-tech Instagram archive

This repository contains scripts to collect Instagram profiles and posts and then renders HTML websites to inspect them. 

The goal is medium and long term archiving. 


## Step 1: Download Instagram posts and profiles

Example for one Instagram accounts:

```
instaloader forummuenchenev --stories --highlights --tagged --reels --comments --no-compress-json --max-connection-attempts 10 --dirname-pattern=data/{target} --filename-pattern={date_utc:%Y}/{typename}_{shortcode}_{date_utc}_UTC  --sanitize-paths --login lead_oe
```

Example for multiple Instagram accounts, stored in a list `01-get-instagram-posts/accounts.txt`.
This uses instaloaders [`args` parameters](https://instaloader.github.io/cli-options.html#cmdoption-arg-args.txt).

```bash
instaloader --stories --highlights --tagged --reels --comments --no-compress-json --max-connection-attempts 10 --dirname-pattern=data/{target} --filename-pattern={date_utc:%Y}/{shortcode}_{date_utc}_UTC  --sanitize-paths --login lead_oe +01-get-instagram-posts/accounts.txt
```

## Step 2: Build static HTML websites

After getting the data, it is used to build static HTML websites. 

```bash
 uv run 02-build-pages/build-html.py
```

## Links

[Using static websites for tiny archives](https://alexwlchan.net/2024/static-websites/)

[pincushion](https://inkdroid.org/2024/10/20/pincushion/)

https://instaloader.github.io/cli-options.html#which-posts-to-download
https://github.com/AdriaPadilla/InstaloaderScripts/tree/master/Instaloader_scripts/get_profile_posts
