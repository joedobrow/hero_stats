# generate_index.py

import os
from git import Repo
from datetime import datetime
import argparse

# Configuration
REPO_PATH = '.'  # Path to your Git repository (current directory)
INDEX_HTML_PATH = 'index.html'  # Path where index.html will be generated
NUM_COMMITS = 8  # Number of latest commits to include in the changelog

# HTML Template Components
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>League of Lads Season 18 Reports</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- Basic CSS Styling -->
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #1e1e1e;
            color: #f0f0f0;
            margin: 0;
            padding: 0 20px;
            position: relative; /* For positioning the timestamp */
        }}
        .report-timestamp {{
            position: absolute;
            top: 10px;
            left: 20px;
            font-size: 14px;
            color: #ccc;
        }}
        .container {{
            max-width: 800px;
            margin: 60px auto 40px; /* Added top margin to accommodate timestamp */
            padding: 40px 0;
            text-align: center;
        }}
        h1 {{
            margin-bottom: 40px;
        }}
        .report-box {{
            background-color: #2e2e2e;
            border: 1px solid #444;
            border-radius: 8px;
            padding: 20px;
            margin: 20px auto;
            width: 80%;
            max-width: 500px;
            transition: background-color 0.3s, transform 0.3s;
        }}
        .report-box:hover {{
            background-color: #3e3e3e;
            transform: scale(1.02);
        }}
        .report-link {{
            display: block;
            background-color: #333;
            color: #1e90ff;
            text-decoration: none;
            padding: 15px;
            border-radius: 6px;
            transition: background-color 0.3s;
        }}
        .report-link:hover {{
            background-color: #444;
        }}
        .report-description {{
            font-size: 16px;
            color: #ccc;
            margin-top: 10px;
        }}
        @media (max-width: 600px) {{
            .report-box {{
                width: 100%;
                padding: 15px;
            }}
            .report-link {{
                padding: 10px;
            }}
            .report-description {{
                font-size: 14px;
            }}
        }}
        /* Changelog Styling */
        .changelog {{
            background-color: #2e2e2e;
            padding: 20px;
            margin-top: 40px;
            border-radius: 8px;
            text-align: left;
        }}
        .changelog h2 {{
            color: #1e90ff;
            text-align: center;
        }}
        .changelog ul {{
            list-style-type: none;
            padding: 0;
        }}
        .changelog li {{
            margin-bottom: 10px;
            border-bottom: 1px solid #444;
            padding-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="report-timestamp">Last Updated: {last_updated}</div>
    <div class="container">
        <h1>League of Lads Season 18 Reports</h1>
        
        <div class="report-box">
            <a href="hero_report.html" class="report-link">
                Hero Report
            </a>
            <p class="report-description">
                Player hero statistics, performance, and rankings.
            </p>
        </div>
        
        <div class="report-box">
            <a href="player_report.html" class="report-link">
                Player Metrics Report
            </a>
            <p class="report-description">
                Comprehensive player metrics and performance over time.
            </p>
        </div>
        
        <div class="report-box">
            <a href="team_analyzer.html" class="report-link">
                Team Analyzer
            </a>
            <p class="report-description">
                Choose the players in a team and see their best heroes and suggested bans.
            </p>
        </div>
        
        <div class="changelog">
            <h2>Changelog</h2>
            <ul>
                {changelog_entries}
            </ul>
        </div>
    </div>
</body>
</html>
'''

def get_latest_commits(repo_path, num_commits=8, branch='main'):
    """
    Retrieves the latest commit messages from the Git repository.

    Args:
        repo_path (str): Path to the Git repository.
        num_commits (int): Number of latest commits to retrieve.
        branch (str): Git branch to fetch commits from.

    Returns:
        list of dict: List containing commit details.
    """
    try:
        repo = Repo(repo_path)
        if repo.bare:
            print("Repository is bare. No commits to retrieve.")
            return []
        # Check if the specified branch exists
        if branch not in repo.heads:
            print(f"Branch '{branch}' does not exist. Available branches: {', '.join(repo.heads)}")
            return []
        commits = list(repo.iter_commits(branch, max_count=num_commits))
        commit_messages = []
        for commit in commits:
            commit_info = {
                'message': commit.message.strip(),
                'author': commit.author.name,
                'date': datetime.fromtimestamp(commit.committed_date).strftime('%Y-%m-%d %H:%M:%S')
            }
            commit_messages.append(commit_info)
        return commit_messages
    except Exception as e:
        print(f"Error retrieving commits: {e}")
        return []

def generate_changelog_html(commit_messages):
    """
    Generates HTML list items for the changelog based on commit messages.

    Args:
        commit_messages (list of dict): List containing commit details.

    Returns:
        str: HTML string of list items.
    """
    if not commit_messages:
        return "<li>No commits available.</li>"
    
    changelog_html = ""
    for commit in commit_messages:
        # Escape HTML characters in commit messages to prevent rendering issues
        message = commit['message'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        author = commit['author'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        changelog_html += f"    <li><strong>{commit['date']}</strong> - <em>{author}</em>: {message}</li>\n"
    return changelog_html

def generate_index_html(last_updated, changelog_entries):
    """
    Generates the complete HTML content for index.html.

    Args:
        last_updated (str): Timestamp of the last update.
        changelog_entries (str): HTML string of changelog list items.

    Returns:
        str: Complete HTML content.
    """
    return HTML_TEMPLATE.format(
        last_updated=last_updated,
        changelog_entries=changelog_entries
    )

def write_index_html(html_content, output_path):
    """
    Writes the HTML content to index.html.

    Args:
        html_content (str): The complete HTML content.
        output_path (str): Path to write the index.html file.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(html_content)
        print(f"index.html generated successfully at {output_path}")
    except Exception as e:
        print(f"Error writing to {output_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Generate a fresh index.html with the latest Git changelog.')
    parser.add_argument('--repo-path', type=str, default='.', help='Path to the Git repository.')
    parser.add_argument('--output', type=str, default='index.html', help='Output path for index.html.')
    parser.add_argument('--num-commits', type=int, default=8, help='Number of latest commits to include in the changelog.')
    parser.add_argument('--branch', type=str, default='main', help='Git branch to fetch commits from.')

    args = parser.parse_args()

    # Get the latest commits
    latest_commits = get_latest_commits(args.repo_path, num_commits=args.num_commits, branch=args.branch)
    
    # Generate changelog HTML
    changelog_html = generate_changelog_html(latest_commits)
    
    # Get current timestamp
    last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Generate complete HTML content
    index_html_content = generate_index_html(last_updated, changelog_html)
    
    # Write to index.html
    write_index_html(index_html_content, args.output)

if __name__ == "__main__":
    main()

