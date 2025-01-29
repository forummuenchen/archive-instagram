import json
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
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
                    image_path = os.path.join(
                        root,
                        f"{base_filename}.jpg",
                    )
                    if os.path.exists(image_path):
                        post["images"].append(os.path.abspath(image_path))

                    for i in range(1, 20):  # Assuming not more than 99 images per post
                        image_name = f"{base_filename}_{i}.jpg"
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


def generate_html_pages(posts_by_year):
    print("\nGenerating HTML pages...")

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader("templates"))
    # Set up Jinja2 environment
    template = env.get_template("post_template.html")

    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    print("Created output directory")

    # Generate a page for each year
    all_years = sorted(posts_by_year.keys())
    for year, posts in posts_by_year.items():
        # Sort posts by timestamp (newest first)
        sorted_posts = sorted(posts, key=lambda x: x["timestamp"], reverse=True)

        print(f"Generating page for {year} ({len(posts)} posts)")

        # Generate HTML
        html_content = template.render(
            year=year, posts=sorted_posts, all_years=all_years
        )

        # Write to file
        output_path = f"output/{year}.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Saved {output_path}")


def main():
    # Directory containing JSON files
    json_directory = "data/forummuenchenev"  # Change this to your directory path

    print("Instagram JSON to HTML Processor")
    print("=" * 30)

    # Process JSON files
    posts_by_year = process_instagram_files(json_directory)

    # Generate HTML pages
    generate_html_pages(posts_by_year)

    print("\nProcess complete!")
    print(
        f"Generated HTML pages for years: {', '.join(map(str, sorted(posts_by_year.keys())))}"
    )
    print("Files are in the 'output' directory")


if __name__ == "__main__":
    main()
