import json
import os
import glob
import shutil
import lzma
import logging
import re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from collections import defaultdict

logging.basicConfig(level=logging.INFO)


class InstagramProcessor:
    def __init__(self, base_directory, base_output_dir, template_dir, static_dir):
        self.base_directory = base_directory
        self.base_output_dir = base_output_dir
        self.template_dir = template_dir
        self.static_dir = static_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.account_post_counts = {}
        self.account_comment_counts = {}

    def load_profile(self, data_dir):
        profile_files = glob.glob(os.path.join(data_dir, "*.json")) + glob.glob(os.path.join(data_dir, "*.json.xz"))
        if not profile_files:
            logging.warning(f"Profile JSON file not found in {data_dir}")
            return {}

        profile_path = profile_files[0]
        try:
            data = self._load_json(profile_path)
        except (KeyError, json.JSONDecodeError, lzma.LZMAError) as e:
            logging.error(f"Error loading profile data from {profile_path}: {e}")
            return {}

        node = data.get("node", {})
        iphone_struct = node.get("iphone_struct", {})

        profile_data = {
            "biography": node.get("biography", ""),
            "bio_links": node.get("external_url", ""),
            "category_name": node.get("category_name", ""),
            "id": node.get("id", ""),
            "full_name": node.get("full_name", ""),
            "public_email": iphone_struct.get("public_email", ""),
            "address_json": node.get("business_address_json", ""),
            "city": iphone_struct.get("city_name", ""),
            "contact_phone_number": node.get("contact_phone_number", ""),
            "follow": node.get("edge_follow", {}).get("count", 0),
            "followed_by": node.get("edge_followed_by", {}).get("count", 0),
            "profile_img": self._find_profile_image(data_dir)
        }

        return profile_data

    def load_posts(self, directory, type):
        logging.info(f"\nScanning directory: {directory} for type: {type}")
        posts_by_year = defaultdict(list)

        files = self.find_files(directory, type)
        logging.info(f"Total files found: {len(files)}")
        total_files = len(files)
        processed_files = 0
        skipped_files = 0

        for file_path in files:
            logging.info(f"Processing file: {file_path}")
            try:
                data = self._load_json(file_path)
            except (KeyError, json.JSONDecodeError, lzma.LZMAError) as e:
                logging.error(f"Error processing {file_path}: {e}")
                skipped_files += 1
                continue

            post = self._extract_post_data(file_path, data, type)
            if not post:
                skipped_files += 1
                continue

            # Ensure no duplicate posts
            if post not in posts_by_year[post["year"]]:
                posts_by_year[post["year"]].append(post)
                processed_files += 1
                logging.info(f"Processing file {processed_files}/{total_files} ({(processed_files/total_files)*100:.1f}%)")

        logging.info("\n\n\nProcessing summary:")
        logging.info(f"Total files found: {total_files + skipped_files}")
        logging.info(f"Files processed: {processed_files}")
        logging.info(f"Files skipped: {skipped_files}")
        logging.info(f"Years found: {sorted(posts_by_year.keys())}")
        logging.info(f"Total posts processed: {sum(len(posts) for posts in posts_by_year.values())}")

        # Save the total number of posts for this account
        self.account_post_counts[os.path.basename(directory)] = sum(len(posts) for posts in posts_by_year.values())

        return posts_by_year

    def generate_post_pages(self, account_name, posts_by_year, tagged_posts_by_year):
        logging.info("\nGenerating HTML pages...")

        try:
            template = self.env.get_template("post.html")
        except TemplateNotFound:
            logging.error("Template 'post.html' not found in the 'templates' directory.")
            return

        account_output_dir = os.path.join(self.base_output_dir, account_name)
        os.makedirs(account_output_dir, exist_ok=True)

        all_years = sorted(posts_by_year.keys())
        for year, posts in posts_by_year.items():
            sorted_posts = sorted(posts, key=lambda x: x["timestamp"], reverse=True)
            logging.info(f"Generating page for {year} ({len(posts)} posts)")

            html_content = template.render(
                year=year,
                posts=sorted_posts,
                all_years=all_years,
                account_name=account_name,
                is_tagged=False
            )

            output_path = os.path.join(account_output_dir, f"{year}.html")
            self._write_to_file(output_path, html_content)
            logging.info(f"Saved {output_path}")

        tagged_all_years = sorted(tagged_posts_by_year.keys())
        for year, posts in tagged_posts_by_year.items():
            sorted_posts = sorted(posts, key=lambda x: x["timestamp"], reverse=True)
            logging.info(f"Generating tagged page for {year} ({len(posts)} posts)")

            html_content = template.render(
                year=year,
                posts=sorted_posts,
                all_years=tagged_all_years,
                account_name=account_name,
                is_tagged=True
            )

            output_path = os.path.join(account_output_dir, f"{year}_tagged.html")
            self._write_to_file(output_path, html_content)
            logging.info(f"Saved {output_path}")

    def generate_account_page(self, account_name, profile, all_years, tagged_all_years):
        logging.info("\nGenerating account page...")

        try:
            template = self.env.get_template("account.html")
        except TemplateNotFound:
            logging.error("Template 'account.html' not found in the 'templates' directory.")
            return

        account_output_dir = os.path.join(self.base_output_dir, account_name)
        os.makedirs(account_output_dir, exist_ok=True)

        html_content = template.render(
            profile=profile,
            all_years=all_years,
            tagged_all_years=tagged_all_years,
            account_name=account_name
        )

        output_path = os.path.join(account_output_dir, "index.html")
        self._write_to_file(output_path, html_content)
        logging.info(f"Saved {output_path}")

    def generate_index_page(self, accounts):
        logging.info("\nGenerating index page...")

        try:
            template = self.env.get_template("index.html")
        except TemplateNotFound:
            logging.error("Template 'index_template.html' not found in the 'templates' directory.")
            return

        # Sort accounts alphabetically and prepare display data
        sorted_accounts = sorted(accounts)
        display_accounts = [{
            'name': account,
            'posts': self.account_post_counts.get(account, 0)
        } for account in sorted_accounts]

        html_content = template.render(accounts=display_accounts)

        output_path = os.path.join(self.base_output_dir, "index.html")
        self._write_to_file(output_path, html_content)
        logging.info(f"Saved {output_path}")

    def copy_static_files(self):
        logging.info("\nCopying static files...")

        output_static_dir = os.path.join(self.base_output_dir, 'static', 'css')
        os.makedirs(output_static_dir, exist_ok=True)

        for css_file in glob.glob(os.path.join(self.static_dir, '*.css')):
            shutil.copy(css_file, output_static_dir)
            logging.info(f"Copied {css_file} to {output_static_dir}")

    def load_accounts(self, base_directory):
        folders = []
        with os.scandir(base_directory) as entries:
            for entry in entries:
                if entry.is_dir():
                    folders.append(entry.name)
        return folders

    def _load_json(self, file_path):
        if file_path.endswith(".xz"):
            with lzma.open(file_path, "rt", encoding="utf-8") as file:
                return json.load(file)
        else:
            with open(file_path, "r", encoding="utf-8") as file:
                return json.load(file)

    def _find_profile_image(self, data_dir):
        profile_pic_files = glob.glob(os.path.join(data_dir, "*profile_pic*"))
        return profile_pic_files[0] if profile_pic_files else ""

    def get_dirs(self, directory, type):
        dirs = [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]
        posts_dirs = [d for d in dirs if re.match(r"20[0-9]{2}", d)]
        tagged_dir = [d for d in dirs if "tagged" in d.lower()]
        highlight_dirs = [d for d in dirs if d not in posts_dirs and d not in tagged_dir]

        if type == "post":
            logging.info(f"Yearly post directories: {posts_dirs}")
            return posts_dirs
        elif type == "tagged":
            if tagged_dir:
                tagged_dir = os.path.join(directory, tagged_dir[0])
                logging.info(f"Tagged directory found: {tagged_dir}")
                return [tagged_dir]
            else:
                logging.info("Tagged directory not found")
                return []
        elif type == "highlight":
            logging.info(f"Highlight directories: {highlight_dirs}")
            return highlight_dirs
        else:
            logging.error(f"Unknown type: {type}")
            return []

    def find_files(self, directory, type, get_comments=False):
        dirs = self.get_dirs(directory, type)
        logging.info(f"Directories: {dirs}")
        files = []
        for dir_path in dirs:
            full_dir_path = os.path.join(directory, dir_path) if type == "post" else dir_path
            if os.path.exists(full_dir_path):
                logging.info(f"Scanning directory: {full_dir_path}")
                dir_files = self.get_files_in_dir(full_dir_path, get_comments)
                files.extend(dir_files)
                logging.info(f"Found {len(dir_files)} files in {full_dir_path}")
        return files

    def get_files_in_dir(self, dir_path, get_comments=False):
        files = []
        for root, _, filenames in os.walk(dir_path):
            for f in filenames:
                if f.endswith(".json") or f.endswith(".json.xz"):
                    if not get_comments and "comments" in f.lower():
                        continue
                    files.append(os.path.join(root, f))
        return files

    def _extract_post_data(self, file_path, data, type="post"):
        node = data.get("node", {})
        timestamp = node.get("date", None) or node.get("taken_at_timestamp", None)
        if timestamp is None:
            logging.error(f"Error processing {file_path}: 'date' or 'taken_at_timestamp' key not found")
            return None

        date_obj = datetime.fromtimestamp(timestamp)
        date = date_obj.strftime("%d.%m.%Y")
        year = date_obj.year

        # Extract caption text
        caption = node.get("caption", None)
        if not caption and "edge_media_to_caption" in node and "edges" in node["edge_media_to_caption"]:
            edges = node["edge_media_to_caption"]["edges"]
            if edges and "node" in edges[0] and "text" in edges[0]["node"]:
                caption = edges[0]["node"]["text"]

        if type == "post":
            post = {
                "caption": caption,
                "comments": node.get("comments", ""),
                "like_count": node.get("edge_media_preview_like", {}).get("count", 0),
                "shortcode": node.get("shortcode", ""),
                "date": date,
                "timestamp": timestamp,
                "year": year,
                "images": self._find_post_images(file_path),
                "accessibility_caption": node.get("accessibility_caption", "")
            }
        elif type == "tagged":
            tagged_users = [tagged_user["node"]["user"]["username"] for tagged_user in node.get("edge_media_to_tagged_user", {}).get("edges", [])]
            owner = node.get("owner", {}).get("username", "")
            post = {
                "caption": node.get("caption", ""),
                "shortcode": node.get("shortcode", ""),
                "date": date,
                "timestamp": timestamp,
                "year": year,
                "images": self._find_post_images(file_path),
                "accessibility_caption": node.get("accessibility_caption", ""),
                "tagged_users": tagged_users,
                "owner": owner
            }
        else:
            logging.error(f"Unknown post type: {type}")
            return None

        return post

    def _find_post_images(self, file_path):
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

    def _write_to_file(self, path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def main():
    processor = InstagramProcessor(
        base_directory="data",
        base_output_dir="instagram-archiv",
        template_dir="templates",
        static_dir="static/css"
    )

    logging.info("Instagram JSON to HTML Processor")
    logging.info("=" * 30)

    accounts = processor.load_accounts(processor.base_directory)
    #accounts = ["forummuenchenev", "philipp.gufler"]
    #accounts = ["philipp.gufler"]
    for account in accounts:
        logging.info(f"Processing account: {account}")
        account_directory = os.path.join(processor.base_directory, account)
        profile_data = processor.load_profile(account_directory)
        posts_by_year = processor.load_posts(account_directory, type="post")
        
        tagged_posts_by_year = processor.load_posts(account_directory, type="tagged")
        processor.generate_post_pages(account, posts_by_year, tagged_posts_by_year)
        all_years = sorted(posts_by_year.keys())
        tagged_all_years = sorted(tagged_posts_by_year.keys())
        processor.generate_account_page(account, profile_data, all_years, tagged_all_years)
        processor.copy_static_files()

    processor.generate_index_page(accounts)
    logging.info("\nProcess complete!")
    logging.info(f"Generated index and HTML pages for accounts: {', '.join(accounts)}")
    logging.info(f"Files are in the {processor.base_output_dir} directory")


if __name__ == "__main__":
    main()