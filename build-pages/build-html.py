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
                    timestamp = data["node"]["taken_at_timestamp"]
                    year = datetime.fromtimestamp(timestamp).year

                    # Extract required fields
                    post = {
                        "caption": (
                            data["node"]["edge_media_to_caption"]["edges"][0]["node"][
                                "text"
                            ]
                            if data["node"]["edge_media_to_caption"]["edges"]
                            else ""
                        ),
                        "comments": data["node"]["comments"],
                        "like_count": data["node"]["edge_media_preview_like"]["count"],
                        "shortcode": data["node"]["shortcode"],
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
    template = env.from_string(
        """
<!DOCTYPE html>
<html>
<head>
    <title>Instagram Posts {{ year }}</title>
    <style>
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            padding: 20px;
        }
        .post {
            border: 1px solid #ccc;
            padding: 15px;
            border-radius: 5px;
        }
        .stats {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
            color: #666;
        }
        .navigation {
            padding: 20px;
            text-align: center;
        }
        .navigation a {
            margin: 0 10px;
            text-decoration: none;
            color: #333;
        }
        .slider {
            position: relative;
            width: 100%;
            max-width: 300px;
        }
        .slides {
            display: flex;
            overflow: hidden;
            width: 100%;
        }
        .slides img {
            min-width: 100%;
            transition: transform 0.5s ease;
        }
        .slider-buttons {
            position: absolute;
            top: 50%;
            width: 100%;
            display: flex;
            justify-content: space-between;
            transform: translateY(-50%);
        }
        .slider-button {
            background-color: rgba(0, 0, 0, 0.5);
            color: white;
            border: none;
            padding: 10px;
            cursor: pointer;
        }
    </style>
    <script>
        function initSliders() {
            document.querySelectorAll('.slider').forEach(function(slider) {
                const slides = slider.querySelector('.slides');
                const images = slides.querySelectorAll('img');
                let currentIndex = 0;

                function showSlide(index) {
                    if (index >= images.length) {
                        currentIndex = 0;
                    } else if (index < 0) {
                        currentIndex = images.length - 1;
                    } else {
                        currentIndex = index;
                    }
                    slides.style.transform = 'translateX(' + (-currentIndex * 100) + '%)';
                }

                slider.querySelector('.prev').addEventListener('click', function() {
                    showSlide(currentIndex - 1);
                });

                slider.querySelector('.next').addEventListener('click', function() {
                    showSlide(currentIndex + 1);
                });
            });
        }

        document.addEventListener('DOMContentLoaded', initSliders);
    </script>
</head>
<body>
    <div class="navigation">
        {% for y in all_years %}
            <a href="{{ y }}.html" {% if y == year %}style="font-weight: bold;"{% endif %}>{{ y }}</a>
        {% endfor %}
    </div>
    <div class="grid">
        {% for post in posts %}
        <div class="post">
        {% if post.images %}
            <div class="slider">
                <div class="slides">
                    {% for image in post.images %}
                    <img src="{{ image }}" alt="Image">
                    {% endfor %}
                </div>
                <div class="slider-buttons">
                    <button class="slider-button prev">❮</button>
                    <button class="slider-button next">❯</button>
                </div>
            </div>
            {% endif %}
            <div>{{ post.caption }}</div>
            
            <div class="stats">
                <span>❤️ {{ post.like_count }}</span>
                <span>💬 {{ post.comments }}</span>
                <a href="https://instagram.com/p/{{ post.shortcode }}" target="_blank">View</a>
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
    """
    )

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
