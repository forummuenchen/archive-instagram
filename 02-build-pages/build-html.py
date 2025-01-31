import json
import os
import glob
import shutil
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from collections import defaultdict

def load_profile(data_dir):
    # Look for profile JSON file with the pattern account_name_numeric_ids.json
    profile_files = glob.glob(os.path.join(data_dir, "*.json"))
    if profile_files:
        profile_path = profile_files[0]
        with open(profile_path, "r") as file:
            data = json.load(file)
        
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
            "followed_by": node.get("edge_followed_by", {}).get("count", 0) 
        }

        # Look for profile picture files
        profile_pic_files = glob.glob(os.path.join(data_dir, "*profile_pic*"))
        if profile_pic_files:
            profile_data["profile_img"] = profile_pic_files[0]
        else:
            profile_data["profile_img"] = ""

        return profile_data
    else:
        print(f"Warning: Profile JSON file not found in {data_dir}")
        return {}

import os
import json
from datetime import datetime
from collections import defaultdict

def process_instagram_files(directory):
    print(f"\nScanning directory: {directory}")
    posts_by_year = defaultdict(list)

    # Count total valid files first
    total_files = sum(
        1
        for root, _, files in os.walk(directory)
        for f in files
        if f.endswith(".json")
        and "tagged" not in f.lower()
        and "comments" not in f.lower()
    )

    processed_files = 0
    skipped_files = 0

    # Process each JSON file
    for root, _, files in os.walk(directory):
        for filename in files:
            # Skip files with 'tagged' or 'comments' in the name
            if (
                "tagged" in filename.lower()
                or "comments" in filename.lower()
                or not filename.endswith(".json")
            ):
                skipped_files += 1
                continue

            processed_files += 1
            print(
                f"\rProcessing file {processed_files}/{total_files} ({(processed_files/total_files)*100:.1f}%)",
                end="",
            )

            with open(os.path.join(root, filename), "r", encoding="utf-8") as file:
                try:
                    data = json.load(file)
                    
                    node = data.get("node", {})
                    timestamp = node.get("date", None)
                    if timestamp is None:
                        raise KeyError("date")

                    date_obj = datetime.fromtimestamp(timestamp)
                    date = date_obj.strftime("%d.%m.%Y")
                    year = date_obj.year

                    caption = node.get("caption", "")
                    comments = node.get("comments", "")
                    like_count = node.get("edge_media_preview_like", {}).get("count", 0)
                    shortcode = node.get("shortcode", "")
                    accessibility_caption = node.get("accessibility_caption", "")

                    # Extract required fields
                    post = {
                        "caption": caption,
                        "comments": comments,
                        "like_count": like_count,
                        "shortcode": shortcode,
                        "date": date,
                        "timestamp": timestamp,
                        "images": [],
                        "accessibility_caption": accessibility_caption
                    }
        
                    # Detect images with the same name as the JSON file
                    base_filename = filename[:-5]  # Remove the .json extension
                    for ext in ["jpg", "webp", "png"]:
                        image_path = os.path.join(root, f"{base_filename}.{ext}")
                        if os.path.exists(image_path):
                            post["images"].append(image_path)

                        for i in range(1, 20):  # Assuming not more than 99 images per post
                            image_name = f"{base_filename}_{i}.{ext}"
                            image_path = os.path.join(root, image_name)
                            if os.path.exists(image_path):
                                post["images"].append(image_path)
                            else:
                                break

                    posts_by_year[year].append(post)
                except (KeyError, json.JSONDecodeError) as e:
                    print(f"\nError processing {filename}: {str(e)}")

    print("\n\nProcessing summary:")
    print(f"Total files found: {total_files + skipped_files}")
    print(f"Files processed: {processed_files}")
    print(f"Files skipped: {skipped_files}")
    print(f"Years found: {sorted(posts_by_year.keys())}")
    print(f"Total posts processed: {sum(len(posts) for posts in posts_by_year.values())}")

    return posts_by_year

def generate_post_pages(account_name, posts_by_year, base_output_dir):
    print("\nGenerating HTML pages...")

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader("templates"))


    try:
        template = env.get_template("post.html")
    except TemplateNotFound:
        print("Template 'post_template.html' not found in the 'templates' directory.")
        return

    account_output_dir = os.path.join(base_output_dir, account_name)
    os.makedirs(account_output_dir, exist_ok=True)

    # Generate a page for each year
    all_years = sorted(posts_by_year.keys())
    for year, posts in posts_by_year.items():
        # Sort posts by timestamp (newest first)
        sorted_posts = sorted(posts, key=lambda x: x["timestamp"], reverse=True)

        print(f"Generating page for {year} ({len(posts)} posts)")

        # Generate HTML
        html_content = template.render(
            year=year,
            posts=sorted_posts,
            all_years=all_years,
            account_name=account_name,
        )

        # Write to file
        output_path = os.path.join(account_output_dir, f"{year}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Saved {output_path}")


def generate_account_page(account_name, profile, all_years, base_output_dir):
    print("\nGenerating account page...")

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader("templates"))
    try:
        template = env.get_template("account.html")
    except TemplateNotFound:
        print(
            "Template 'account_template.html' not found in the 'templates' directory."
        )
        return

    account_output_dir = os.path.join(base_output_dir, account_name)
    os.makedirs(account_output_dir, exist_ok=True)

    # Generate HTML
    html_content = template.render(
        profile=profile,
        all_years=all_years,
        account_name=account_name
    )

    # Write to file
    output_path = os.path.join(account_output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved {output_path}")


def generate_index_page(accounts, base_output_dir):
    print("\nGenerating index page...")

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader("templates"))
    try:
        template = env.get_template("index.html")
    except TemplateNotFound:
        print("Template 'index_template.html' not found in the 'templates' directory.")
        return

    # Generate HTML
    html_content = template.render(accounts=accounts)

    # Write to file
    output_path = os.path.join(base_output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved {output_path}")


def copy_static_files(static_dir, main_output_dir):
    print("\nCopying static files...")

    # Create the static directory in the main output directory if it doesn't exist
    output_static_dir = os.path.join(main_output_dir, 'static', 'css')
    os.makedirs(output_static_dir, exist_ok=True)

    # Copy all the CSS files
    for css_file in glob.glob(os.path.join(static_dir, '*.css')):
        shutil.copy(css_file, main_output_dir)
        print(f"Copied {css_file} to {output_static_dir}")


def load_folders(base_directory):
    folders = []
    with os.scandir(base_directory) as entries:
        for entry in entries:
            if entry.is_dir():
                folders.append(entry.name)
    return folders

def main():
    # Base directory containing account directories
    base_directory = "data"
    base_output_dir = "instagram-archiv"
     # List all account directories: all folders within base_directory
    accounts = load_folders(base_directory)
    #accounts = ["lez_lesbischqueereszentrum", "forummuenchenev"]

    print("Instagram JSON to HTML Processor")
    print("=" * 30)

    for account in accounts:
        account_directory = os.path.join(base_directory, account)
        print(f"Processing account: {account}")
        profile_data = load_profile(account_directory)
        posts_by_year = process_instagram_files(account_directory)
        generate_post_pages(account, posts_by_year, base_output_dir)
        all_years = sorted(posts_by_year.keys())
        generate_account_page(account, profile_data, all_years, base_output_dir)

        # Copy static CSS files to the output directory
        copy_static_files("static/css", os.path.join(base_output_dir))

    # Generate index page
    generate_index_page(accounts, base_output_dir)

    print("\nProcess complete!")
    print(f"Generated index and HTML pages for accounts: {', '.join(accounts)}")
    print(f"Files are in the {base_output_dir} directory")


if __name__ == "__main__":
    main()