"""
Redd Baron is a tool that allows investigators to fetch and analyze comments made by a specific Reddit user. It
gathers information including the subreddits they are active in,the posts they have commented on, and the content of
their comments. It then presents the information in a user-friendly format. This is callable from tool_runner.py and
the web interface.
"""

import sys
import requests


def fetch_reddit_comments_json(user):
    url = f"https://www.reddit.com/user/{user}/comments/.json?&limit=200&&after=&count=0&_=1710475616698"
    response = requests.get(url, headers={"User-agent": "Random"})
    return response.json()


def fetch_reddit_posts_json(user):
    url = f"https://www.reddit.com/user/{user}/submitted/.json?&limit=200&&after=&count=0&_=1710475616698"
    response = requests.get(url, headers={"User-agent": "Random"})
    return response.json()


def extract_comments_info(comment_data):
    comments_info = []

    for child in comment_data["data"]["children"]:
        data = child["data"]
        comment_info = {
            "comment_url": data['link_permalink'],
            "subreddit": data["subreddit"],
            "link_author": data["link_author"],
            "link_title": data["link_title"],
            "comment_body": data["body"],
            "comment_author": data["author"],
            "created_utc": data["created_utc"]
        }
        comments_info.append(comment_info)

    return comments_info


def extract_posts_info(post_data):
    posts_info = []

    for child in post_data["data"]["children"]:
        data = child["data"]
        post_info = {
            "post_url": data['permalink'],
            "subreddit": data["subreddit"],
            "post_title": data["title"],
            "post_body": data.get("selftext", ""),
            "post_author": data["author"],
            "created_utc": data["created_utc"],
            "num_comments": data["num_comments"]
        }
        posts_info.append(post_info)

    return posts_info


def main():
    try:
        target_user = sys.argv[1]
    except IndexError:
        print("Usage: python3 reddbaron.py <username>")
        sys.exit(1)

    comment_data = fetch_reddit_comments_json(target_user)
    all_comments = extract_comments_info(comment_data)

    post_data = fetch_reddit_posts_json(target_user)
    all_posts = extract_posts_info(post_data)

    print("POSTS")
    print("-" * 40 + "\n")
    for post in all_posts:
        info_lines = [
            f"Subreddit: {post['subreddit']}",
            f"Post Author: {post['post_author']}",
            f"Post Title: {post['post_title']}",
            "Post Body: " + post["post_body"],
            f"Created UTC: {post['created_utc']}",
            f"Post URL: {post['post_url']}",
            "-" * 40,
        ]

        for line in info_lines:
            print(line)

    print("\nCOMMENTS")
    print("-" * 40 + "\n")
    for comment in all_comments:
        info_lines = [
            f"Subreddit: {comment['subreddit']}",
            f"Post Author: {comment['link_author']}",
            f"Post Title: {comment['link_title']}",
            "Comment Body: " + comment["comment_body"],
            f"Comment Author: {comment['comment_author']}",
            f"Created UTC: {comment['created_utc']}",
            f"Comment URL: {comment['comment_url']}",
            "-" * 40,
        ]

        for line in info_lines:
            print(line)


if __name__ == "__main__":
    main()
