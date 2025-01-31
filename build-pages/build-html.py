import json
import os
import glob
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
            profile_data = {
                "biography": data["node"]["biography"],
                "bio_links": data["node"]["external_url"],
                "category_name": data["node"]["category_name"],
                "id": data["node"]["id"],
                "contact_phone_number": data["node"]["iphone_struct"]["contact_phone_number"],
                "full_name":data["node"]["full_name"],
                "public_email": data["node"]["iphone_struct"]["public_email"],
                "address_json": data["node"]["business_address_json"],
                "city": data["node"]["iphone_struct"]["city_name"]
            }
            
        profile_pic_files = glob.glob(os.path.join(data_dir, "*profile_pic*"))
        profile_data["profile_img"] = profile_pic_files[0]

        return profile_data
    else:
        print(f"Warning: Profile JSON file not found in {data_dir}")
        return {}


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
                    # Extract timestamp and convert to year
                    timestamp = data["node"]["date"]
                    date_obj = datetime.fromtimestamp(timestamp)
                    date = date_obj.strftime("%d.%m.%Y")
                    year = datetime.fromtimestamp(timestamp).year
                    print(date)
                    # Extract required fields
                    post = {
                        "caption": data["node"]["caption"],
                        "comments": data["node"]["comments"],
                        "like_count": data["node"]["edge_media_preview_like"]["count"],
                        "shortcode": data["node"]["shortcode"],
                        "date": date,
                        "timestamp": timestamp,
                        "images": [],
                    }

                    # Detect images with the same name as the JSON file
                    base_filename = filename[:-5]  # Remove the .json extension
                    for ext in ["jpg", "webp", "png"]:
                        image_path = os.path.join(
                            root,
                            f"{base_filename}.{ext}",
                        )
                        if os.path.exists(image_path):
                            post["images"].append(os.path.abspath(image_path))

                        for i in range(
                            1, 20
                        ):  # Assuming not more than 99 images per post
                            image_name = f"{base_filename}_{i}.{ext}"
                            image_path = os.path.join(root, image_name)
                            if os.path.exists(image_path):
                                post["images"].append(os.path.abspath(image_path))
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
    print(
        f"Total posts processed: {sum(len(posts) for posts in posts_by_year.values())}"
    )

    return posts_by_year


def generate_html_pages(account_name, posts_by_year, base_output_dir):
    print("\nGenerating HTML pages...")

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader("templates"))
    try:
        template = env.get_template("post_template.html")
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
        years=all_years,
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
        template = env.get_template("index_template.html")
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


def main():
    # Base directory containing account directories
    base_directory = "data"
    base_output_dir = "output"
     # List all account directories: all folders within base_directory
    accounts = [
        "forummuenchenev",
        "lez_lesbischqueereszentrum",
        "sub_szene_muc"
    ] 

    print("Instagram JSON to HTML Processor")
    print("=" * 30)

    for account in accounts:
        account_directory = os.path.join(base_directory, account)
        print(f"Processing account: {account}")
        profile_data = load_profile(account_directory)
        posts_by_year = process_instagram_files(account_directory)
        generate_html_pages(account, posts_by_year, base_output_dir)
        all_years = sorted(posts_by_year.keys())
        generate_account_page(account, profile_data, all_years, base_output_dir)

    # Generate index page
    generate_index_page(accounts, base_output_dir)

    print("\nProcess complete!")
    print(f"Generated index and HTML pages for accounts: {', '.join(accounts)}")
    print("Files are in the 'output' directory")


if __name__ == "__main__":
    main()
