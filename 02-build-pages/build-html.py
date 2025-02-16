import json
import os
import glob
import shutil
import lzma
import logging
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

    def load_posts(self, directory):
        logging.info(f"\nScanning directory: {directory}")
        posts_by_year = defaultdict(list)

        files = [f for f in self._find_files(directory, type="post")]
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

            post = self._extract_post_data(file_path, data)
            if not post:
                skipped_files += 1
                continue

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

    def generate_post_pages(self, account_name, posts_by_year):
        logging.info("\nGenerating HTML pages...")

        try:
            template = self.env.get_template("posts_per_year.html")
        except TemplateNotFound:
            logging.error("Template 'post_template.html' not found in the 'templates' directory.")
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
            )

            output_path = os.path.join(account_output_dir, f"{year}.html")
            self._write_to_file(output_path, html_content)
            logging.info(f"Saved {output_path}")

    def generate_account_page(self, account_name, profile, all_years):
        logging.info("\nGenerating account page...")

        try:
            template = self.env.get_template("account.html")
        except TemplateNotFound:
            logging.error("Template 'account_template.html' not found in the 'templates' directory.")
            return

        account_output_dir = os.path.join(self.base_output_dir, account_name)
        os.makedirs(account_output_dir, exist_ok=True)

        html_content = template.render(
            profile=profile,
            all_years=all_years,
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

    def load_folders(self, base_directory):
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

    def _find_files(self, directory, type):
        for root, _, files in os.walk(directory):
            for f in files:
                if type == "post":
                    if f.endswith(".json") or f.endswith(".json.xz"):
                        if "tagged" in f.lower() or "comments" in f.lower():
                            logging.debug(f"Skipping file due to filter: {f}")
                            continue
                        yield os.path.join(root, f)
                elif type == "comment":
                    if f.endswith("-comments.json") or f.endswith("-comments.json.gz"):
                        yield os.path.join(root, f)
                elif type == "tagged":
                    if "tagged" in f.lower() and f.endswith(".json"):
                        yield os.path.join(root, f)

    def _extract_post_data(self, file_path, data):
        node = data.get("node", {})
        timestamp = node.get("date", None)
        if timestamp is None:
            logging.error(f"Error processing {file_path}: 'date' key not found")
            return None

        date_obj = datetime.fromtimestamp(timestamp)
        date = date_obj.strftime("%d.%m.%Y")
        year = date_obj.year

        post = {
            "caption": node.get("caption", ""),
            "comments": node.get("comments", ""),
            "like_count": node.get("edge_media_preview_like", {}).get("count", 0),
            "shortcode": node.get("shortcode", ""),
            "date": date,
            "timestamp": timestamp,
            "year": year,
            "images": self._find_post_images(file_path),
            "accessibility_caption": node.get("accessibility_caption", "")
        }
        return post

    def _find_post_images(self, file_path):
        images = []
        base_filename = os.path.splitext(file_path)[0]
        for ext in ["jpg", "webp", "png"]:
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

    accounts = processor.load_folders(processor.base_directory)
    accounts = ["munichkyivqueer", "forummuenchenev"]
    for account in accounts:
        logging.info(f"Processing account: {account}")
        account_directory = os.path.join(processor.base_directory, account)
        profile_data = processor.load_profile(account_directory)
        posts_by_year = processor.load_posts(account_directory)
        processor.generate_post_pages(account, posts_by_year)
        all_years = sorted(posts_by_year.keys())
        processor.generate_account_page(account, profile_data, all_years)
        processor.copy_static_files()

    processor.generate_index_page(accounts)
    logging.info("\nProcess complete!")
    logging.info(f"Generated index and HTML pages for accounts: {', '.join(accounts)}")
    logging.info(f"Files are in the {processor.base_output_dir} directory")


if __name__ == "__main__":
    main()