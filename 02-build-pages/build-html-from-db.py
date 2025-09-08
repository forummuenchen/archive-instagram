import json
import os
import glob
import shutil
import lzma
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from collections import defaultdict

logging.basicConfig(level=logging.INFO)

class InstagramProcessor:
    def __init__(self, base_directory, base_output_dir, template_dir, static_dir, db, account_tbl, posts_metadata_tbl, posts_tbl, connections_tbl):
        self.base_directory = base_directory
        self.base_output_dir = base_output_dir
        self.template_dir = template_dir
        self.static_dir = static_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.account_post_counts = {}
        self.account_comment_counts = {}
        self.db = db
        self.account_tbl = account_tbl
        self.posts_metadata_tbl = posts_metadata_tbl
        self.posts_tbl = posts_tbl
        self.connections_tbl = connections_tbl

    def load_accounts(self, con, account_tbl):
        """
        Load accounts from the database.
        """
        cursor = con.cursor()
        cursor.execute(f"SELECT DISTINCT username, full_name, biography, br_category, is_private FROM {account_tbl}")
        accounts = []
        for row in cursor.fetchall():
            accounts.append({
                "username": row[0],
                "full_name": row[1],
                "biography": row[2],
                "br_category": row[3],
                "is_private": row[4]
            })
        return accounts
    
    def load_profile(self, con, username):
        """
        Load profile data for a specific account from the database.
        """
        cursor = con.cursor()
        cursor.execute(f"SELECT * FROM {self.account_tbl} WHERE username = ?", (username,))
        profile_data = cursor.fetchone()
        
        return profile_data
    
    def find_profile_image(self, account_name):
        profile_pic_files = glob.glob(os.path.join(self.base_directory, account_name, "*profile_pic*"))
        
        return profile_pic_files[0] if profile_pic_files else ""
    
    def find_post_images(self, file_path):
        images = []
        base_filename = os.path.splitext(file_path)[0]
        if base_filename.endswith(".json"):
            base_filename = base_filename[:-5]
        elif base_filename.endswith(".json.xz"):
            base_filename = base_filename[:-8]
        
        for ext in ["jpg", "webp", "png", "mp4"]:
            image_path = f"{base_filename}.{ext}"
            if os.path.exists(image_path):
                images.append(image_path)
            for i in range(1, 20):
                image_name = f"{base_filename}_{i}.{ext}"
                image_path = f"{image_name}"
                if os.path.exists(image_path):
                    images.append(image_path)
                else:
                    break
        return images
    
    def load_count_tbl(self, con):
        """
        Load the count of posts types for all accounts from the database and return a dictionary.
        """
        cursor = con.cursor()
        cursor.execute(f"SELECT DISTINCT username, type, COUNT(*) as count FROM {self.posts_metadata_tbl} GROUP BY type, username ORDER BY count DESC, username, type")
        count_res = cursor.fetchall()

        # create dict from query result
        counts_dict = {}
        for username, typ, count in count_res:
            if username not in counts_dict:
                counts_dict[username] = {}
            counts_dict[username][typ] = count

        return counts_dict
    
    def load_recent_posts(self, con, months=1):
        """
        Lädt alle Posts der letzten 'months' Monate, sortiert absteigend nach Datum.
        Gibt eine Liste von Post-Dicts zurück.
        """
        cursor = con.cursor()
        since = datetime.now() - timedelta(days=months*30)

        cursor.execute(
            f"""
            SELECT DISTINCT p.*, m.year, m.username
            FROM {self.posts_tbl} p
            JOIN {self.posts_metadata_tbl} m ON p.path = m.path
            WHERE p.timestamp >= ?
            """,
            (int(since.timestamp()),)
        )
        posts = cursor.fetchall()
        shortcodes = [post['shortcode'] for post in posts]
        tagged_dict, mentioned_dict, commented_dict = self.get_connections_for_posts(con, shortcodes)
        post_dicts = []
        for post in posts:
            post_dict = dict(post)
            post_dict['images'] = self.find_post_images(post['path'])
            post_dict['tagged_users'] = tagged_dict.get(post['shortcode'], [])
            post_dict['mentioned_users'] = mentioned_dict.get(post['shortcode'], [])
            post_dict['commented_users'] = commented_dict.get(post['shortcode'], [])
            post_dict['date'] = datetime.fromtimestamp(post['timestamp']).strftime('%Y-%m-%d')
            post_dict['username'] = post['username']
            post_dicts.append(post_dict)
        
        post_dicts.sort(key=lambda x: x['timestamp'], reverse=True)
        return post_dicts
    
    
    def load_posts_by_year(self, con, username, type="post"):
        cursor = con.cursor()
        cursor.execute(
            f"""
            SELECT DISTINCT p.*, m.year
            FROM {self.posts_tbl} p
            JOIN {self.posts_metadata_tbl} m ON p.path = m.path
            WHERE m.username = ? AND p.type = ?
            """,
            (username, type)
        )
        posts = cursor.fetchall()
        shortcodes = [post['shortcode'] for post in posts]
        tagged_dict, mentioned_dict, commented_dict = self.get_connections_for_posts(con, shortcodes)
        posts_by_year = defaultdict(list)
        for post in posts:
            year = post['year']
            post_dict = dict(post)
            post_dict['images'] = self.find_post_images(post['path'])
            post_dict['tagged_users'] = tagged_dict.get(post['shortcode'], [])
            post_dict['mentioned_users'] = mentioned_dict.get(post['shortcode'], [])
            post_dict['commented_users'] = commented_dict.get(post['shortcode'], [])
            if year:
                posts_by_year[year].append(post_dict)
        return posts_by_year
    
    def load_posts_by_dir(self, con, username, type="highlight"):
        cursor = con.cursor()
        cursor.execute(
            f"""
            SELECT DISTINCT p.*, m.dir
            FROM {self.posts_tbl} p
            JOIN {self.posts_metadata_tbl} m ON p.path = m.path
            WHERE m.username = ? AND p.type = ?
            """,
            (username, type)
        )
        posts = cursor.fetchall()
        shortcodes = [post['shortcode'] for post in posts]
        tagged_dict, mentioned_dict, commented_dict = self.get_connections_for_posts(con, shortcodes)
        posts_by_dir = defaultdict(list)
        for post in posts:
            dir = post['dir']
            post_dict = dict(post)
            post_dict['images'] = self.find_post_images(post['path'])
            post_dict['tagged_users'] = tagged_dict.get(post['shortcode'], [])
            post_dict['mentioned_users'] = mentioned_dict.get(post['shortcode'], [])
            post_dict['commented_users'] = commented_dict.get(post['shortcode'], [])
            if dir:
                posts_by_dir[dir].append(post_dict)
        return posts_by_dir
    
    def get_connections_for_posts(self, con, shortcodes):
        """
        Returns dictionaries of connections for the given shortcodes.
        - tagged_dict: {shortcode: [usernames]}
        - mentioned_dict: {shortcode: [usernames]}
        - commented_dict: {shortcode: [usernames]}
        """
        if not shortcodes:
            return defaultdict(list), defaultdict(list), defaultdict(list)
        cursor = con.cursor()
        placeholder = ",".join("?" for _ in shortcodes)
        cursor.execute(
            f"""
            SELECT DISTINCT shortcode, username, type
            FROM {self.connections_tbl}
            WHERE shortcode IN ({placeholder})
            """,
            shortcodes
        )
        connections = cursor.fetchall()
        tagged_dict = defaultdict(list)
        mentioned_dict = defaultdict(list)
        commented_dict = defaultdict(list)
        for row in connections:
            if row['type'] == 'tagged_by_other_user':
                tagged_dict[row['shortcode']].append(row['username'])
            elif row['type'] == 'mentioned_by_user':
                mentioned_dict[row['shortcode']].append(row['username'])
            elif row['type'] == 'commented_post_by_user':
                commented_dict[row['shortcode']].append(row['username'])
        return tagged_dict, mentioned_dict, commented_dict
    
    def generate_post_pages(self, account_name, posts_by_year, tagged_posts_by_year, highlight_posts_by_dir):
        #logging.info("Generating HTML pages...")

        try:
            template = self.env.get_template("post.html")
        except TemplateNotFound:
            logging.error("Template 'post.html' not found in the 'templates' directory.")
            return

        account_output_dir = os.path.join(self.base_output_dir, account_name)
        os.makedirs(account_output_dir, exist_ok=True)

        # create posts HTML pages for each year
        all_years = sorted(posts_by_year.keys())
        
        for year, posts in posts_by_year.items():
            sorted_posts = sorted(posts, key=lambda x: x["timestamp"], reverse=True)
            #logging.info(f"Generating page for {year} ({len(posts)} posts)")

            html_content = template.render(
                year=year,
                posts=sorted_posts,
                all_years=all_years,
                account_name=account_name,
                is_tagged=False,
                css_path="../static/css/styles.css"
            )

            output_path = os.path.join(account_output_dir, f"{year}.html")
            self.write_to_file(output_path, html_content)
            #logging.info(f"Saved {output_path}")
        
        # create tagged posts HTML pages for each year
        tagged_all_years = sorted(tagged_posts_by_year.keys())
        for year, posts in tagged_posts_by_year.items():
            sorted_posts = sorted(posts, key=lambda x: x["timestamp"], reverse=True)
            #logging.info(f"Generating tagged page for {year} ({len(posts)} posts)")

            html_content = template.render(
                year=year,
                posts=sorted_posts,
                all_years=tagged_all_years,
                account_name=account_name,
                is_tagged=True,
                css_path="../static/css/styles.css"
            )

            output_path = os.path.join(account_output_dir, f"{year}_tagged.html")
            self.write_to_file(output_path, html_content)
            #logging.info(f"Saved {output_path}")

        for dir, posts in highlight_posts_by_dir.items():
            sorted_posts = sorted(posts, key=lambda x: x["timestamp"], reverse=True)
            #logging.info(f"Generating highlight page for {dir} ({len(posts)} posts)")

            html_content = template.render(
                dir=dir,
                posts=sorted_posts,
                all_years=highlight_posts_by_dir,
                account_name=account_name,
                is_highlight=True,
                css_path="../static/css/styles.css"
            )

            output_path = os.path.join(account_output_dir, f"{dir}_highlight.html")
            self.write_to_file(output_path, html_content)
            #logging.info(f"Saved {output_path}")

    def generate_account_page(self, account_name, profile, all_years, tagged_all_years, highlight_posts_by_dir, story_posts_by_year):
        #logging.info(f"Generating account page... for {account_name}")

        try:
            template = self.env.get_template("account.html")
        except TemplateNotFound:
            logging.error("Template 'account.html' not found in the 'templates' directory.")
            return

        account_output_dir = os.path.join(self.base_output_dir, account_name)
        os.makedirs(account_output_dir, exist_ok=True)
        
        html_content = template.render(
            account_name=account_name,
            profile=profile,
            profile_img = self.find_profile_image(account_name),
            all_years=all_years,
            tagged_all_years=tagged_all_years,
            highlight_posts_by_dir = highlight_posts_by_dir,
            story_posts_by_year = story_posts_by_year,
            css_path="../static/css/styles.css"
        )

        output_path = os.path.join(account_output_dir, "index.html")
        self.write_to_file(output_path, html_content)
        #logging.info(f"Saved {output_path}")

    def generate_index_page(self, accounts, accounts_count, all_months):
        logging.info("\nGenerating index page...")

        try:
            template = self.env.get_template("index.html")
        except TemplateNotFound:
            logging.error("Template 'index.html' not found in the 'templates' directory.")
            return

        accounts = sorted(accounts, key=lambda a: a["username"].lower())

        html_content = template.render(
            accounts=accounts,
            counts=accounts_count,
            all_months=all_months,
            css_path="static/css/styles.css"
        )

        output_path = os.path.join(self.base_output_dir, "index.html")
        self.write_to_file(output_path, html_content)
        #logging.info(f"Saved {output_path}")


    def get_posts_by_month(self, con, months=36):
        """
        Gibt ein Dict {YYYY/MM: [posts]} und eine sortierte Liste aller Monate zurück.
        """
        posts = self.load_recent_posts(con, months=months)
        posts_by_month = defaultdict(list)
        for post in posts:
            year = datetime.fromtimestamp(post['timestamp']).year
            month = datetime.fromtimestamp(post['timestamp']).month
            key = f"{year:04d}/{month:02d}"
            posts_by_month[key].append(post)
        all_months = sorted(posts_by_month.keys(), reverse=True)
        return posts_by_month, all_months

    def generate_monthly_feed_pages(self, con):
        posts_by_month, all_months = self.get_posts_by_month(con, months=36)

        for idx, key in enumerate(all_months):
            year, month = key.split("/")
            posts = posts_by_month[key]
            prev_key = all_months[idx + 1] if idx + 1 < len(all_months) else None
            next_key = all_months[idx - 1] if idx > 0 else None

            template = self.env.get_template("feed_month.html")
            html_content = template.render(
                posts=posts,
                year=year,
                month=month,
                prev_key=prev_key,
                next_key=next_key,
                all_months=all_months,
                css_path="../../static/css/styles.css"
            )
            output_path = os.path.join(self.base_output_dir, "feed", year, f"{month}.html")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            self.write_to_file(output_path, html_content)

    def copy_static_files(self):
        #logging.info("\nCopying static files...")

        output_static_dir = os.path.join(self.base_output_dir, 'static', 'css')
        os.makedirs(output_static_dir, exist_ok=True)

        for css_file in glob.glob(os.path.join(self.static_dir, '*.css')):
            shutil.copy(css_file, output_static_dir)
            #logging.info(f"Copied {css_file} to {output_static_dir}")

    def write_to_file(self, path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    
def main():
    processor = InstagramProcessor(
        base_directory="data",
        base_output_dir="instagram-archiv",
        template_dir="templates",
        static_dir="static/css",
        db = "data/instagram.sqlite",
        account_tbl = "archive_account",
        posts_metadata_tbl = "archive_files_metadata",
        posts_tbl = "archive_files",
        connections_tbl = "archive_connections"
    )

    logging.info("Instagram JSON to HTML Processor")
    logging.info("=" * 30)

    con = sqlite3.connect(processor.db)
    con.row_factory = sqlite3.Row
    accounts = processor.load_accounts(con, processor.account_tbl)
    exclude_accounts = ["andreagibson", "adrian_krenn", "misc", "test"]
    accounts = [a for a in accounts if a["username"] not in exclude_accounts]
    accounts_count = processor.load_count_tbl(con)

    #accounts = ["niederbayerische_division"]#, "sportimsueden23", "1schulztim"] 

    # start generating HTML pages
    posts_by_month, all_months = processor.get_posts_by_month(con, months=200)
    processor.generate_index_page(accounts, accounts_count, all_months)

    for account in accounts:
        if account not in exclude_accounts:
            logging.info(f"Processing account: {account["username"]}")
            
            profile_data = processor.load_profile(con, account["username"])
            posts_by_year = processor.load_posts_by_year(con, account["username"], type="post")
            tagged_posts_by_year = processor.load_posts_by_year(con, account["username"], type="tagged")
            story_posts_by_year = processor.load_posts_by_year(con, account["username"], type="story")
            highlight_posts_by_dir = processor.load_posts_by_dir(con, account["username"], type="highlight")
            # generate account pages
            processor.generate_account_page(account["username"], profile_data, posts_by_year, tagged_posts_by_year, highlight_posts_by_dir, story_posts_by_year)
            # generate post pages
            processor.generate_post_pages(account["username"], posts_by_year, tagged_posts_by_year, highlight_posts_by_dir)
            # copy static files
            processor.copy_static_files()

    processor.generate_monthly_feed_pages(con)
    processor.copy_static_files()
    logging.info(f"Files are in the {processor.base_output_dir} directory")
    con.close()

if __name__ == "__main__":
    main()