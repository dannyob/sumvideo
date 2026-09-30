#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "jinja2",
#   "yt-dlp",
#   "python-slugify",
# ]
# ///

import argparse
import base64
import html
import json
import logging
import os
import re
import subprocess
import sys
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import yt_dlp
from jinja2 import Environment, FileSystemLoader
from slugify import slugify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('sumvideo')

# Constants
VIDEO_EXTENSIONS = ['mp4', 'webm', 'ogg', 'mov']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
THUMBNAIL_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
MAX_TITLE_LENGTH = 40
MAX_DESCRIPTION_LENGTH = 150
DEFAULT_VIDEO_FORMAT = 'mp4'
SITE_NAME = 'SumVideo Archive'
INDEX_FILENAME = 'index.html'
# Pages show their tags in a block that `--index` regenerates from the
# video:tag meta lines, so those lines stay the one place tags are edited
TAGS_START = '<!-- sumvideo:tags (generated from the video:tag lines; edit those) -->'
TAGS_END = '<!-- /sumvideo:tags -->'
DEFAULT_STYLE = 'newyork'

# CSS Styles - modular design allows for easy style switching
STYLE_BUBBLEGUM = """
        /* 🧁 Bubblegum Aesthetic - Soft, Playful, and Modern */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&family=Quicksand:wght@500;700&display=swap');

        :root {
            --bg-primary: #fde8f4;
            --bg-secondary: #fef4f9;
            --color-primary: #f9c0e0;
            --color-accent: #c4f0e4;
            --color-text: #4a3f5a;
            --color-text-light: #7a6f8a;
            --color-link: #e88bb8;
            --color-link-hover: #d66a9f;
            --border-radius: 24px;
            --border-radius-sm: 16px;
            --shadow-soft: 0 8px 24px rgba(249, 192, 224, 0.15);
            --shadow-hover: 0 12px 32px rgba(249, 192, 224, 0.25);
            --gradient-primary: linear-gradient(135deg, #e88bb8 0%, #c4a7e7 50%, #89cff0 100%);
            --gradient-accent: linear-gradient(135deg, #c4f0e4 0%, #e0f7f1 100%);
        }

        * {
            box-sizing: border-box;
        }

        body {
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.7;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 24px;
            background: var(--bg-primary);
            color: var(--color-text);
            font-weight: 300;
        }

        h1 {
            font-family: 'Quicksand', 'Poppins', sans-serif;
            font-weight: 700;
            font-size: 1.8em;
            margin: 0 0 1.5rem 0;
            color: var(--color-text);
            background: var(--gradient-primary);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1.3;
            letter-spacing: -0.02em;
        }

        .video-container {
            width: 100%;
            margin: 2rem 0;
            border-radius: var(--border-radius);
            overflow: hidden;
            box-shadow: var(--shadow-soft);
            background: white;
            padding: 8px;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .video-container:hover {
            transform: translateY(-4px);
            box-shadow: var(--shadow-hover);
        }

        video {
            width: 100%;
            max-height: 600px;
            border-radius: var(--border-radius-sm);
            display: block;
        }

        .metadata {
            background: var(--gradient-accent);
            padding: 2rem;
            border-radius: var(--border-radius);
            margin: 2rem 0;
            box-shadow: var(--shadow-soft);
            border: 2px solid rgba(255, 255, 255, 0.8);
        }

        .metadata p {
            margin: 0.75rem 0;
            font-size: 1em;
        }

        .metadata strong {
            font-weight: 600;
            color: var(--color-text);
        }

        .source {
            margin-top: 2.5rem;
            padding: 1.5rem;
            background: var(--bg-secondary);
            border-radius: var(--border-radius-sm);
            border-left: 4px solid var(--color-primary);
        }

        a {
            color: var(--color-link);
            text-decoration: none;
            font-weight: 400;
            transition: all 0.2s ease;
            position: relative;
        }

        a:hover {
            color: var(--color-link-hover);
            transform: translateY(-1px);
        }

        a::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            width: 0;
            height: 2px;
            background: var(--gradient-primary);
            transition: width 0.3s ease;
        }

        a:hover::after {
            width: 100%;
        }

        .archive-note {
            border-top: 2px solid rgba(249, 192, 224, 0.2);
            margin-top: 3rem;
            padding-top: 2rem;
            font-size: 0.9em;
            color: var(--color-text-light);
            text-align: center;
        }

        .download-section {
            margin-top: 2rem;
            padding: 2rem;
            background: var(--gradient-primary);
            border-radius: var(--border-radius);
            box-shadow: var(--shadow-soft);
        }

        .download-section.hidden {
            display: none;
        }

        .download-section p {
            margin: 0 0 1rem 0;
            font-weight: 600;
            color: var(--color-text);
        }

        .download-button {
            display: inline-block;
            padding: 12px 24px;
            margin: 8px 8px 8px 0;
            background: white;
            color: var(--color-text);
            border-radius: 999px;
            cursor: pointer;
            font-weight: 500;
            font-family: 'Poppins', sans-serif;
            border: 2px solid rgba(249, 192, 224, 0.3);
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(249, 192, 224, 0.2);
        }

        .download-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(249, 192, 224, 0.35);
            background: var(--bg-primary);
            border-color: var(--color-primary);
        }

        .download-button:active {
            transform: translateY(-1px);
        }

        /* Floating blob decorations */
        body::before {
            content: '';
            position: fixed;
            top: -150px;
            right: -150px;
            width: 400px;
            height: 400px;
            background: radial-gradient(circle at 30% 30%, rgba(249, 192, 224, 0.2), rgba(255, 214, 243, 0.1));
            border-radius: 50%;
            filter: blur(60px);
            z-index: -1;
            pointer-events: none;
        }

        body::after {
            content: '';
            position: fixed;
            bottom: -150px;
            left: -150px;
            width: 400px;
            height: 400px;
            background: radial-gradient(circle at 70% 70%, rgba(196, 240, 228, 0.2), rgba(224, 247, 241, 0.1));
            border-radius: 50%;
            filter: blur(60px);
            z-index: -1;
            pointer-events: none;
        }

        /* Responsive design */
        @media (max-width: 600px) {
            body {
                padding: 24px 16px;
            }

            h1 {
                font-size: 1.5em;
            }

            .metadata, .download-section {
                padding: 1.5rem;
            }
        }
"""

STYLE_NEWYORK = """
        /* 📰 New Yorker Style - Classic, Elegant, Timeless */
        @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&family=Lato:wght@400;700&display=swap');

        :root {
            --bg-primary: #f7f5f0;
            --bg-secondary: #edeae3;
            --color-accent: #2c2c2c;
            --color-text: #1a1a1a;
            --color-text-light: #666;
            --color-border: #d0d0d0;
            --color-link: #c41e3a;
            --color-link-hover: #8b1428;
        }

        * {
            box-sizing: border-box;
        }

        body {
            font-family: 'Merriweather', Georgia, serif;
            line-height: 1.8;
            max-width: 680px;
            margin: 0 auto;
            padding: 60px 40px;
            background: var(--bg-primary);
            color: var(--color-text);
            font-weight: 300;
            font-size: 17px;
        }

        h1 {
            font-family: 'Lato', 'Helvetica Neue', sans-serif;
            font-weight: 700;
            font-size: 1.5em;
            line-height: 1.25;
            margin: 0 0 0.5em 0;
            color: var(--color-accent);
            letter-spacing: -0.02em;
            border-bottom: 3px solid var(--color-accent);
            padding-bottom: 0.5em;
        }

        .video-container {
            width: 100%;
            margin: 2.5em 0;
            border: 1px solid var(--color-border);
            background: #000;
        }

        video {
            width: 100%;
            max-height: 600px;
            display: block;
        }

        .metadata {
            margin: 2.5em 0;
            padding: 1.5em 0;
            border-top: 1px solid var(--color-border);
            border-bottom: 1px solid var(--color-border);
            font-family: 'Lato', 'Helvetica Neue', sans-serif;
            font-size: 0.9em;
            line-height: 1.6;
        }

        .metadata p {
            margin: 0.5em 0;
        }

        .metadata strong {
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.85em;
            color: var(--color-text-light);
        }

        .source {
            margin-top: 2.5em;
            padding: 1.5em;
            background: var(--bg-secondary);
            border-left: 3px solid var(--color-accent);
            font-size: 0.9em;
        }

        .source p {
            margin: 0;
            font-family: 'Lato', sans-serif;
        }

        a {
            color: var(--color-link);
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: border-bottom-color 0.2s ease;
        }

        a:hover {
            border-bottom-color: var(--color-link);
        }

        .archive-note {
            margin-top: 3em;
            padding-top: 2em;
            border-top: 1px solid var(--color-border);
            font-size: 0.85em;
            color: var(--color-text-light);
            text-align: center;
            font-family: 'Lato', sans-serif;
            font-style: italic;
        }

        .download-section {
            margin-top: 2em;
            padding: 1.5em;
            background: var(--bg-secondary);
            border: 1px solid var(--color-border);
        }

        .download-section.hidden {
            display: none;
        }

        .download-section p {
            margin: 0 0 1em 0;
            font-family: 'Lato', sans-serif;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.85em;
        }

        .download-button {
            display: inline-block;
            padding: 10px 20px;
            margin: 0 10px 10px 0;
            background: var(--color-accent);
            color: white;
            border: 2px solid var(--color-accent);
            cursor: pointer;
            font-family: 'Lato', sans-serif;
            font-weight: 700;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: all 0.2s ease;
        }

        .download-button:hover {
            background: white;
            color: var(--color-accent);
        }

        /* Responsive design */
        @media (max-width: 600px) {
            body {
                padding: 40px 20px;
                font-size: 16px;
            }

            h1 {
                font-size: 1.3em;
            }
        }
"""

STYLE_DEFAULT = """
        :root {
            --bg: #fafaf8;
            --fg: #1f2328;
            --muted: #656d76;
            --rule: #e4e4e0;
            --panel: #f1f1ed;
            --accent: #0b62c4;
            --accent-hover: #084e9e;
            --on-accent: #fff;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #16181b;
                --fg: #e6e6e3;
                --muted: #9aa0a6;
                --rule: #2c2f33;
                --panel: #1f2226;
                --accent: #6aa8f0;
                --accent-hover: #8dbdf4;
                --on-accent: #0d1117;
            }
        }
        * { box-sizing: border-box; }
        body {
            max-width: 860px;
            margin: 0 auto;
            padding: 32px 20px 48px;
            background: var(--bg);
            color: var(--fg);
            font: 17px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                  "Helvetica Neue", Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
        }
        h1 {
            font-size: 1.6rem;
            line-height: 1.25;
            margin: 0 0 20px;
        }
        .video-container {
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.18);
        }
        video {
            display: block;
            width: 100%;
            max-height: 75vh;
            background: #000;
        }
        .metadata { margin: 20px 0; }
        .metadata p { margin: 0 0 16px; }
        .metadata .creator,
        .metadata .published {
            display: inline-block;
            margin: 0 24px 12px 0;
        }
        .metadata strong {
            color: var(--muted);
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-right: 0.4em;
        }
        .metadata .description-label { display: none; }
        a { color: var(--accent); text-decoration: none; }
        a:hover { text-decoration: underline; }
        .source {
            font-size: 0.9rem;
            color: var(--muted);
        }
        .source p { margin: 0; }
        .download-section {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 24px;
            padding: 16px;
            background: var(--panel);
            border-radius: 8px;
        }
        .download-section.hidden { display: none; }
        .download-section .download-label { display: none; }
        .download-button {
            font: inherit;
            font-size: 0.9rem;
            font-weight: 600;
            padding: 8px 16px;
            color: var(--on-accent);
            background: var(--accent);
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }
        .download-button:hover { background: var(--accent-hover); }
        .archive-note {
            border-top: 1px solid var(--rule);
            margin-top: 40px;
            padding-top: 14px;
            font-size: 0.85rem;
            color: var(--muted);
        }
        .archive-note p { margin: 4px 0; }
"""

# Style dictionary for easy access
STYLES = {
    'bubblegum': STYLE_BUBBLEGUM,
    'newyork': STYLE_NEWYORK,
    'default': STYLE_DEFAULT,
}

# HTML template for the description page
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    
    <!-- Open Graph metadata for rich previews -->
    <meta property="og:title" content="{{ title }}">
    <meta property="og:type" content="video.other">
    <meta property="og:description" content="{{ short_description }}">
    {% if og_image_url %}
    <meta property="og:image" content="{{ og_image_url }}">
    {% endif %}
    {% if page_url %}
    <meta property="og:url" content="{{ page_url }}">
    {% endif %}
    <meta property="og:site_name" content="{{ site_name }}">
    {% for tag in tags %}
    <meta property="video:tag" content="{{ tag }}">
    {% endfor %}
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:creator" content="{{ uploader }}">
    <style>
        /* Base rules shared by every style */
        .description { white-space: pre-line; }
        h1, .description, .source, .archive-note { overflow-wrap: anywhere; }
        .sumvideo-tags { font-size: 0.9em; }
{{ styles }}
    </style>
    {% if is_standalone %}
    <script>
        function downloadFile(dataUrl, filename) {
            const link = document.createElement('a');
            link.href = dataUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        
        function downloadVideo() {
            const videoDataUrl = document.getElementById('video-player').querySelector('source').src;
            downloadFile(videoDataUrl, "{{ video_filename }}");
        }
        
        function downloadJSON() {
            const jsonData = atob("{{ json_data_base64 }}");
            // Using a properly formatted JSON string
            const blob = new Blob([jsonData], {type: 'application/json'});
            const dataUrl = URL.createObjectURL(blob);
            // Use the same base filename as the HTML file
            downloadFile(dataUrl, "{{ html_filename }}.info.json");
        }
    </script>
    {% endif %}
</head>
<body>
    <h1>{{ title }}</h1>
    
    <div class="video-container">
        <video id="video-player" controls preload="metadata"
               {%- if poster_url %} poster="{{ poster_url }}"{% endif %}>
            <source src="{{ video_data_url if is_standalone else video_filename }}" type="{{ video_mimetype }}">
            Your browser does not support the video tag. Dagnabbit!
        </video>
    </div>

    <div class="metadata">
        <p class="creator"><strong>Creator:</strong> {{ uploader }}</p>
        <p class="published"><strong>Published:</strong> {{ upload_date }}</p>
        {% if description %}
        <p class="description-label"><strong>Description:</strong></p>
        <p class="description">{{ description }}</p>
        {% endif %}
    </div>
    {% if tags_block %}
    {{ tags_block }}
    {% endif %}
    
    <div class="source">
        <p>Original source: <a href="{{ webpage_url }}" target="_blank">{{ webpage_url }}</a></p>
    </div>
    <div class="download-section{% if not is_standalone %} hidden{% endif %}">
        <p class="download-label"><strong>Download Files:</strong></p>
        <button class="download-button" onclick="downloadVideo()">Download Video</button>
        <button class="download-button" onclick="downloadJSON()">Download JSON Metadata</button>
    </div>
 
    <div class="archive-note">
        <p>This is an archived copy of <a href="{{ webpage_url }}" target="_blank">the original content</a>, saved on {{ archive_date }} by <a href="https://github.com/dannyob/sumvideo" target="_blank">sumvideo</a>.</p>
        {% if is_standalone %}
        <p>This is a standalone HTML file with embedded video and JSON data.</p>
        {% endif %}
    </div>
</body>
</html>"""

# HTML template for the index of all pages in a directory
INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ site_name }}</title>
    <meta property="og:title" content="{{ site_name }}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="{{ site_name }}">
    {% if page_url %}
    <meta property="og:url" content="{{ page_url }}">
    {% endif %}
    <style>
        :root {
            --bg: #fafaf8;
            --fg: #1f2328;
            --muted: #656d76;
            --rule: #e4e4e0;
            --panel: #f1f1ed;
            --accent: #0b62c4;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #16181b;
                --fg: #e6e6e3;
                --muted: #9aa0a6;
                --rule: #2c2f33;
                --panel: #1f2226;
                --accent: #6aa8f0;
            }
        }
        * { box-sizing: border-box; }
        body {
            max-width: 860px;
            margin: 0 auto;
            padding: 32px 20px 48px;
            background: var(--bg);
            color: var(--fg);
            font: 17px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                  "Helvetica Neue", Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
        }
        h1 { font-size: 1.6rem; margin: 0 0 4px; }
        .summary { color: var(--muted); font-size: 0.9rem; margin: 0 0 24px; }
        ol { list-style: none; margin: 0; padding: 0; }
        li {
            display: grid;
            grid-template-columns: 160px 1fr;
            gap: 16px;
            align-items: start;
            padding: 14px 0;
            border-top: 1px solid var(--rule);
        }
        .thumb {
            display: block;
            aspect-ratio: 16 / 9;
            border-radius: 6px;
            overflow: hidden;
            background: var(--panel);
        }
        .thumb img { display: block; width: 100%; height: 100%; object-fit: cover; }
        .title {
            color: var(--fg);
            font-weight: 600;
            text-decoration: none;
            overflow-wrap: anywhere;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .title:hover { color: var(--accent); }
        .meta { color: var(--muted); font-size: 0.85rem; margin: 4px 0 0; }
        @media (max-width: 480px) {
            li { grid-template-columns: 112px 1fr; gap: 12px; }
            body { font-size: 16px; }
        }
        .tags a, .tag { color: var(--accent); text-decoration: none; }
        .tags a:hover, .tag:hover { text-decoration: underline; }
        .tags { font-size: 0.9rem; margin: 0 0 20px; line-height: 2; }
        .tags .count { color: var(--muted); font-size: 0.8rem; margin-right: 10px; }
        .tag { font-size: 0.8rem; margin-left: 8px; }
        /* Filtering without JavaScript: a tag link targets its anchor below,
           and these rules hide every entry without that tag. */
        {% for tag in tags %}
        #tag-{{ tag.slug }}:target ~ ol > li:not(.t-{{ tag.slug }}) { display: none; }
        #tag-{{ tag.slug }}:target ~ nav a[href="#tag-{{ tag.slug }}"] { color: var(--fg); font-weight: 700; }
        {% endfor %}
    </style>
</head>
<body>
    <h1>{{ site_name }}</h1>
    {% for tag in tags %}<span id="tag-{{ tag.slug }}"></span>{% endfor %}
    <p class="summary">{{ pages|length }} video{{ '' if pages|length == 1 else 's' }},
        updated {{ updated }}</p>
    {% if tags %}
    <nav class="tags"><a href="#">All</a> <span class="count">{{ pages|length }}</span>
        {%- for tag in tags %}
        <a href="#tag-{{ tag.slug }}">{{ tag.name }}</a> <span class="count">{{ tag.count }}</span>
        {%- endfor %}
    </nav>
    {% endif %}
    <ol>
    {% for page in pages %}
        <li class="{{ page.classes }}">
            <a class="thumb" href="{{ page.href }}" tabindex="-1" aria-hidden="true">
                {%- if page.thumbnail_src %}<img src="{{ page.thumbnail_src }}" alt="" loading="lazy">{% endif -%}
            </a>
            <div>
                <a class="title" href="{{ page.href }}">{{ page.title }}</a>
                <p class="meta">
                    {{- page.creator }}{% if page.creator and page.published %} &middot; {% endif %}{{ page.published -}}
                    {%- for slug, name in page.tag_links %}<a class="tag" href="#tag-{{ slug }}">{{ name }}</a>{% endfor -%}
                </p>
            </div>
        </li>
    {% endfor %}
    </ol>
</body>
</html>"""

def format_date(date_str: str) -> str:
    """Format date from YYYYMMDD to ISO format (YYYY-MM-DD)."""
    try:
        return date.fromisoformat(date_str).isoformat()
    except ValueError:
        return date_str

def clean_title_hashtags(title: str) -> str:
    """
    Clean up title by removing hashtags while preserving meaningful content.
    
    Args:
        title: Original title that may contain hashtags
        
    Returns:
        Cleaned title with hashtags removed but main content preserved
    """
    if not title:
        return title
    
    # Split by hashtags and take the part before the first hashtag
    # This preserves the main content while removing social media tags
    parts = title.split('#')
    main_content = parts[0].strip()
    
    # If the main content is too short, it might be just emojis or very brief
    # In that case, we might want to keep some context
    if len(main_content.strip()) < 10 and len(parts) > 1:
        # Look for the first meaningful hashtag that might be part of the content
        for part in parts[1:]:
            part = part.strip()
            if part and not part.lower().startswith(('fyp', 'viral', 'trend', 'for', 'you')):
                # Add back the first meaningful hashtag as it might be content-related
                main_content = f"{main_content} #{part.split()[0]}"
                break
    
    # Clean up extra whitespace and return
    return main_content.strip() if main_content.strip() else title

def generate_short_slug(title: str, upload_date: str | None = None) -> str:
    """
    Generate a shortened, meaningful slug from a title with optional date suffix.
    
    Args:
        title: Original title to shorten
        upload_date: Optional upload date in YYYYMMDD format for uniqueness
        
    Returns:
        Shortened slug suitable for filenames
    """
    if not title:
        title = "untitled"
        
    # Truncate title to a reasonable length
    short_title = title[:MAX_TITLE_LENGTH].strip()
    
    # Remove trailing ellipsis if present
    if short_title.endswith('...'):
        short_title = short_title[:-3].strip()
    
    # Add unique identifier based on upload date if available
    unique_suffix = ''
    if upload_date and len(upload_date) >= 4:
        # Use just the last 4 digits of upload date for uniqueness
        unique_suffix = f"-{upload_date[-4:]}"
    
    # Create and return the slugified result
    return slugify(short_title) + unique_suffix

def get_mime_type(file_extension: str) -> str:
    """
    Return the MIME type based on file extension.
    
    Args:
        file_extension: The extension of the file (without dot)
        
    Returns:
        MIME type string for the video format
    """
    mime_types = {
        'mp4': 'video/mp4',
        'webm': 'video/webm',
        'ogg': 'video/ogg',
        'mov': 'video/quicktime',
    }
    return mime_types.get(file_extension.lower(), 'video/mp4')

def video_index(url: str) -> int:
    """
    Which video of a multi-video post a URL points at, e.g. .../status/123/video/2.

    Args:
        url: The video URL

    Returns:
        The 1-based index from the URL, or 1 if it names none
    """
    match = re.search(r'/video/(\d+)/?(?:[?#]|$)', url)
    return int(match.group(1)) if match and int(match.group(1)) > 0 else 1

def downloaded_file(metadata: dict[str, Any]) -> Path | None:
    """
    The file yt-dlp reports it downloaded.

    Args:
        metadata: Video metadata from yt-dlp

    Returns:
        Path to the downloaded file, or None if yt-dlp didn't report one that exists
    """
    for download in metadata.get('requested_downloads') or []:
        if download.get('filepath') and Path(download['filepath']).exists():
            return Path(download['filepath'])
    return None

def download_video(url: str, output_dir: str | Path, format: str = DEFAULT_VIDEO_FORMAT, 
                  cookies_from_browser: str | None = None, cookies_file: str | None = None,
                  keep_all: bool = False) -> dict[str, Any] | None:
    """
    Download a video using yt-dlp and return its metadata.
    
    Args:
        url: URL of the video to download
        output_dir: Directory to save the video
        format: Video format to download
        cookies_from_browser: Browser to extract cookies from (chrome, firefox, safari, etc.)
        cookies_file: Path to Netscape format cookie file
        keep_all: Keep the separate video/audio streams after they are merged
    
    Returns:
        Dictionary containing video metadata or None if download failed
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Set up yt-dlp options
    ydl_opts = {
        'format': f'bestvideo[ext={format}]+bestaudio[ext=m4a]/best[ext={format}]/best',
        'paths': {'home': str(output_path)},
        # Let yt-dlp use its naming pattern for initial download, we'll rename later
        'outtmpl': {'default': '%(title)s.%(ext)s'},
        'writeinfojson': True,
        'writethumbnail': True,
        # Some sites (TikTok) serve thumbnails yt-dlp names ".image"; make them all .jpg
        'postprocessors': [{'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg', 'when': 'before_dl'}],
        # Separate video/audio streams are deleted after merging unless --keep-all
        'keepvideo': keep_all,
        # A post with several videos is a playlist to yt-dlp; fetch just one
        'playlist_items': str(video_index(url)),
        # ...and write no info.json or thumbnail for the post as a whole
        'allow_playlist_files': False,
    }
    
    # Add cookie options if provided
    if cookies_from_browser:
        ydl_opts['cookiesfrombrowser'] = (cookies_from_browser,)
        logger.info(f"Using cookies from browser: {cookies_from_browser}")
    elif cookies_file:
        ydl_opts['cookiefile'] = cookies_file
        logger.info(f"Using cookies from file: {cookies_file}")
    
    try:
        # Download the video
        logger.info(f"Downloading video from {url} to {output_path}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            
            if result is None:
                logger.error(f"Could not extract information from {url}")
                return None
                
            if result.get('_type') == 'playlist' or 'entries' in result:
                entries = [entry for entry in result.get('entries') or [] if entry]
                if not entries:
                    logger.error(f"No videos downloaded from {url}")
                    return None
                result = entries[0]
            logger.info(f"Successfully downloaded video: {result.get('title', 'Unknown')}")
            return result
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error downloading video: {e}")
        return None
    except Exception:
        logger.exception("An unexpected error occurred")
        return None

def get_file_as_base64(file_path: str | Path) -> str:
    """
    Convert file content to base64 string.
    
    Args:
        file_path: Path to the file (string or Path object)
        
    Returns:
        Base64 encoded string of file content
        
    Raises:
        IOError: If file cannot be read
    """
    path_obj = Path(file_path) if isinstance(file_path, str) else file_path
    
    try:
        with path_obj.open('rb') as file:
            return base64.b64encode(file.read()).decode('utf-8')
    except OSError as e:
        logger.error(f"Failed to read file for base64 encoding: {path_obj} - {e}")
        raise

def get_image_mime_type(file_path: str | Path) -> str:
    """
    Determine the MIME type of an image based on its extension.
    
    Args:
        file_path: Path to the image file (string or Path object)
        
    Returns:
        MIME type string for the image
    """
    path_obj = Path(file_path) if isinstance(file_path, str) else file_path
    ext = path_obj.suffix.lower()
    
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
    }
    return mime_types.get(ext, 'image/jpeg')  # Default to JPEG if unknown

def public_url(base_url: str, filename: str) -> str:
    """
    Build the public URL of a file in the output directory.

    Args:
        base_url: URL where the output directory is served
        filename: Name of a file in that directory

    Returns:
        Absolute URL with the filename percent-encoded
    """
    return f"{base_url.rstrip('/')}/{quote(filename)}"

def thumbnail_files(directory: Path, stem: str) -> list[Path]:
    """
    List the thumbnail files named after a video, as they are actually named on disk.

    Listing the directory (instead of testing guessed names) matters on
    case-insensitive filesystems, where "clip.JPG" exists whenever "clip.jpg" does.

    Args:
        directory: Directory containing the video
        stem: Video filename without its extension

    Returns:
        Matching thumbnail paths, in THUMBNAIL_EXTENSIONS order
    """
    found = [f for f in directory.iterdir()
             if f.stem == stem and f.suffix.lower() in THUMBNAIL_EXTENSIONS]
    return sorted(found, key=lambda f: THUMBNAIL_EXTENSIONS.index(f.suffix.lower()))

def find_thumbnail(directory: Path, stem: str) -> Path | None:
    """
    Find the thumbnail yt-dlp saved alongside a video.

    Args:
        directory: Directory containing the video
        stem: Video filename without its extension

    Returns:
        Path to the thumbnail, or None if there isn't one
    """
    found = thumbnail_files(directory, stem)
    return found[0] if found else None

def ensure_jpeg_thumbnail(thumbnail_path: Path) -> Path:
    """
    Convert a thumbnail to JPEG with ffmpeg; link previews handle JPEG most reliably.

    Args:
        thumbnail_path: Path to the downloaded thumbnail

    Returns:
        Path to the JPEG thumbnail, or the original path if it is already a JPEG
        or conversion failed
    """
    if thumbnail_path.suffix.lower() in ('.jpg', '.jpeg'):
        return thumbnail_path
    jpeg_path = thumbnail_path.with_suffix('.jpg')
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(thumbnail_path), str(jpeg_path)],
                       check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as e:
        logger.warning(f"Could not convert {thumbnail_path.name} to JPEG, keeping it as is: {e}")
        return thumbnail_path
    thumbnail_path.unlink()
    return jpeg_path

def index_url(base_url: str | None) -> str:
    """
    Address of the index from a page in the same directory.

    Args:
        base_url: Public URL of the directory, if known

    Returns:
        The index's absolute URL, or its relative filename
    """
    return public_url(base_url, INDEX_FILENAME) if base_url else INDEX_FILENAME

def tag_block(tags: list[str], index_href: str | None) -> str:
    """
    Build the visible tag list for a page, between its generated-block markers.

    Args:
        tags: The page's tags
        index_href: Address of the index to link each tag to, or None for plain text

    Returns:
        HTML for the block; just the markers if there are no tags
    """
    items = []
    for tag in tags:
        name, slug = html.escape(tag), slugify(tag)
        if index_href and slug:
            items.append(f'<a href="{html.escape(index_href)}#tag-{slug}">{name}</a>')
        else:
            items.append(f'<span>{name}</span>')
    # Commas, not CSS, separate the tags: older pages lack the stylesheet rules
    inner = f'\n<p class="sumvideo-tags">Tags: {", ".join(items)}</p>\n' if items else '\n'
    return f'{TAGS_START}{inner}{TAGS_END}'

TAG_BLOCK = re.compile(r'<!-- sumvideo:tags\b.*?<!-- /sumvideo:tags -->', re.DOTALL)
METADATA_DIV = re.compile(r'<div class="metadata">.*?</div>', re.DOTALL)

def sync_tag_block(html_path: Path, tags: list[str], index_href: str) -> bool:
    """
    Make a page's visible tag block match its tags, rewriting the file only if needed.

    Pages without a block get one after their metadata, but only if they have tags.

    Args:
        html_path: The page
        tags: Tags from the page's video:tag lines
        index_href: Address of the index to link tags to

    Returns:
        True if the file was changed
    """
    text = html_path.read_text(encoding='utf-8')
    block = tag_block(tags, index_href)
    if TAG_BLOCK.search(text):
        new_text = TAG_BLOCK.sub(lambda _: block, text, count=1)
    elif tags:
        metadata = METADATA_DIV.search(text)
        if not metadata:
            logger.warning(f"No metadata block to put tags after in {html_path.name}")
            return False
        new_text = f"{text[:metadata.end()]}\n    {block}{text[metadata.end():]}"
    else:
        return False
    if new_text == text:
        return False
    html_path.write_text(new_text, encoding='utf-8')
    return True

def create_html(metadata: dict[str, Any], video_path: str | Path, output_dir: str | Path,
              standalone: bool = False, style: str = DEFAULT_STYLE,
              base_url: str | None = None, tags: list[str] | None = None) -> str:
    """
    Create an HTML description page for the video.

    Args:
        metadata: Video metadata from yt-dlp
        video_path: Path to the downloaded video file
        output_dir: Directory to save the HTML file
        standalone: Whether to create a standalone HTML file with embedded data
        style: Style name to use for the HTML page (default: newyork)
        base_url: Public URL of output_dir; makes og:image and og:url absolute
        tags: Tags for the page, each written as a video:tag meta line

    Returns:
        Path to the created HTML file
    """
    # Convert paths to Path objects
    video_path_obj = Path(video_path) if isinstance(video_path, str) else video_path
    output_dir_obj = Path(output_dir) if isinstance(output_dir, str) else output_dir
    
    # Extract relevant metadata
    raw_title = metadata.get('title', 'Untitled Video')
    description = metadata.get('description', '')
    
    # For truncated titles (ending with '...'), try to use description as title if it looks more complete
    title = raw_title
    # yt-dlp numbers the videos of a multi-video post ("... #1"); ignore that here
    if (re.sub(r'\s#\d+$', '', raw_title).endswith('...') and description
            and len(description.strip()) > len(raw_title)):
        # Use the description as the title, but clean it up
        cleaned_desc = description.strip()
        # If description is significantly longer and appears to contain the full content, use it
        if len(cleaned_desc) > len(raw_title) + 10:  # At least 10 chars longer than truncated title
            title = cleaned_desc
    
    # Clean up the title by removing hashtags while preserving the main content
    title = clean_title_hashtags(title)
    
    uploader = metadata.get('uploader', 'Unknown')
    upload_date = format_date(metadata.get('upload_date', ''))
    webpage_url = metadata.get('webpage_url', '')
    
    # Create a shortened description for OG metadata
    # Only hide description if we actually used the full description as the title
    # (not just when title was cleaned of hashtags)
    display_description = '' if title == description else description
    short_description = display_description
    if display_description and len(display_description) > MAX_DESCRIPTION_LENGTH:
        short_description = display_description[:MAX_DESCRIPTION_LENGTH] + '...'
    
    # Get video filename and MIME type
    video_filename = video_path_obj.name
    
    # URL encode the filename to handle special characters in HTML
    url_safe_filename = quote(video_filename)
    
    # Get the file extension and MIME type
    file_extension = video_path_obj.suffix[1:]  # Remove the dot
    video_mimetype = get_mime_type(file_extension)
    
    # Prepare data for standalone mode and rich previews
    video_data_url = ""
    json_data_base64 = ""
    
    # Get the base filename for associated files (without extension)
    base_filename = video_path_obj.stem
    
    # Get thumbnail path directly from metadata if available
    thumbnail_path = None
    if metadata.get('thumbnail'):
        thumbnail_str = str(metadata['thumbnail'])
        potential_thumbnail = Path(thumbnail_str)
        if potential_thumbnail.exists():
            thumbnail_path = potential_thumbnail
        else:
            # Try to find the thumbnail in the output directory with the same filename
            potential_thumbnail = output_dir_obj / Path(thumbnail_str).name
            if potential_thumbnail.exists():
                thumbnail_path = potential_thumbnail
    
    # If no thumbnail path from metadata, try to derive it from yt-dlp naming pattern
    if not thumbnail_path:
        # yt-dlp typically names the thumbnail with the same base name as the video
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            potential_path = output_dir_obj / f"{base_filename}{ext}"
            if potential_path.exists():
                thumbnail_path = potential_path
                break
    
    # Standalone pages embed the thumbnail once, as the poster. Link previews can't
    # use an embedded image, so they get no og:image. Normal pages reference the file.
    poster_url = ""
    og_image_url = ""
    if thumbnail_path and standalone:
        try:
            thumbnail_mime = get_image_mime_type(thumbnail_path)
            thumbnail_base64 = get_file_as_base64(thumbnail_path)
            poster_url = f"data:{thumbnail_mime};base64,{thumbnail_base64}"
        except OSError as e:
            logger.error(f"Error embedding thumbnail: {e}")
    elif thumbnail_path:
        poster_url = quote(thumbnail_path.name)
        og_image_url = public_url(base_url, thumbnail_path.name) if base_url else poster_url
    
    if standalone:
        try:
            # Use the exact video path provided rather than searching
            if video_path_obj.exists():
                video_base64 = get_file_as_base64(video_path_obj)
                video_data_url = f"data:{video_mimetype};base64,{video_base64}"
            else:
                logger.warning(f"Video file not found for standalone mode: {video_path_obj}")
            
            # Get JSON path derived from metadata
            json_file_path = output_dir_obj / f"{base_filename}.info.json"
            
            if json_file_path.exists():
                try:
                    # Load and pretty-print the JSON data with indentation
                    json_content = json_file_path.read_text(encoding='utf-8')
                    json_data = json.loads(json_content)
                    formatted_json = json.dumps(json_data, indent=2)
                    json_data_base64 = base64.b64encode(formatted_json.encode('utf-8')).decode('utf-8')
                except (OSError, ValueError) as e:
                    logger.error(f"Error processing JSON file: {e}")
        except OSError:
            logger.exception("Error preparing standalone data")
    
    # Generate a shorter, meaningful slug for the filename
    slug = generate_short_slug(title, metadata.get('upload_date'))
    html_filename = f"{slug}.html"
    html_path = output_dir_obj / html_filename
    page_url = public_url(base_url, html_filename) if base_url else ""

    # Select the style CSS
    style_css = STYLES.get(style, STYLES[DEFAULT_STYLE])

    # Create Jinja2 environment and template
    # Disable autoescape to prevent double-escaping of HTML entities
    env = Environment(
        loader=FileSystemLoader(searchpath="./"),
        autoescape=False
    )
    template = env.from_string(HTML_TEMPLATE)

    # Render the template with ISO date format for archive date
    archive_date = datetime.now().astimezone().strftime("%Y-%m-%d")

    html_content = template.render(
        title=title,
        uploader=uploader,
        upload_date=upload_date,
        description=display_description,
        short_description=short_description,
        webpage_url=webpage_url,
        video_filename=url_safe_filename,
        video_mimetype=video_mimetype,
        archive_date=archive_date,
        is_standalone=standalone,
        video_data_url=video_data_url,
        json_data_base64=json_data_base64,
        html_filename=slug,  # HTML filename without extension
        og_image_url=og_image_url,  # Thumbnail for rich previews
        poster_url=poster_url,
        page_url=page_url,
        site_name=SITE_NAME,
        # The page template doesn't autoescape; tags are free text
        tags=[html.escape(tag) for tag in tags or []],
        # A standalone page may be saved anywhere, so only link to an index
        # whose public address is known
        tags_block=tag_block(tags, None if standalone and not base_url
                             else index_url(base_url)) if tags else '',
        styles=style_css  # Inject the selected style
    )
    
    # Write the HTML file
    try:
        html_path.write_text(html_content, encoding='utf-8')
        logger.info(f"Created HTML file: {html_path}")
    except OSError as e:
        logger.error(f"Error writing HTML file: {e}")
    
    return str(html_path)

# This function has been removed as we now directly derive filenames from yt-dlp output
# rather than searching for files by extension

class _PageInfoParser(HTMLParser):
    """Collect the parts of a sumvideo page needed for the index."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.poster = ""
        self.has_archive_note = False
        self.tags: list[str] = []
        self.paragraphs: list[str] = []
        self._in_title = False
        self._paragraph: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == 'meta':
            key = attributes.get('property') or attributes.get('name')
            if key == 'video:tag':
                self.tags.append(attributes.get('content') or "")
            elif key:
                self.meta[key] = attributes.get('content') or ""
        elif tag == 'title':
            self._in_title = True
        elif tag == 'video':
            self.poster = attributes.get('poster') or ""
        elif tag == 'p':
            self._paragraph = []
        elif tag == 'div' and 'archive-note' in (attributes.get('class') or '').split():
            self.has_archive_note = True

    def handle_endtag(self, tag: str) -> None:
        if tag == 'title':
            self._in_title = False
        elif tag == 'p' and self._paragraph is not None:
            self.paragraphs.append("".join(self._paragraph).strip())
            self._paragraph = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._paragraph is not None:
            self._paragraph.append(data)

def read_page_info(html_path: Path) -> dict[str, Any] | None:
    """
    Read the title, creator, date and thumbnail from a sumvideo page.

    Args:
        html_path: Path to an HTML file

    Returns:
        Dictionary with filename, title, creator, published, thumbnail (a local
        filename, or "" if the page has none or embeds it) and tags (a list), or
        None if the file is not a sumvideo page
    """
    try:
        text = html_path.read_text(encoding='utf-8', errors='replace')
    except OSError as e:
        logger.warning(f"Could not read {html_path.name}: {e}")
        return None
    # Standalone pages embed megabytes of base64; drop it before parsing
    text = re.sub(r'(data:[\w/+.-]+;base64,)[A-Za-z0-9+/=]+', r'\1', text)
    text = re.sub(r'atob\("[A-Za-z0-9+/=]*"\)', 'atob("")', text)
    parser = _PageInfoParser()
    parser.feed(text)
    # Pages from before Open Graph support have no og:site_name, but every
    # version has written the archive note
    if parser.meta.get('og:site_name') != SITE_NAME and not parser.has_archive_note:
        return None

    def labelled(label: str) -> str:
        for paragraph in parser.paragraphs:
            if paragraph.startswith(label):
                return paragraph[len(label):].strip()
        return ""

    poster = parser.poster
    return {
        'filename': html_path.name,
        'title': parser.title.strip() or html_path.stem,
        'creator': parser.meta.get('twitter:creator') or labelled('Creator:'),
        'published': labelled('Published:'),
        'thumbnail': "" if not poster or poster.startswith('data:') else unquote(poster),
        'tags': [tag.strip() for tag in parser.tags if tag.strip()],
    }

def index_tags(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Count the tags used across pages, for the index's filter links.

    Tags that slugify the same way ("Cats", "cats") are counted together under
    the first spelling seen.

    Args:
        pages: Page entries with a tag_links list of (slug, name) pairs

    Returns:
        One dictionary per tag with slug, name and count, most used first
    """
    names: dict[str, str] = {}
    counts: dict[str, int] = {}
    for page in pages:
        for slug, name in dict(page['tag_links']).items():
            names.setdefault(slug, name)
            counts[slug] = counts.get(slug, 0) + 1
    return [{'slug': slug, 'name': names[slug], 'count': counts[slug]}
            for slug in sorted(counts, key=lambda slug: (-counts[slug], slug))]

def build_index(directory: Path, base_url: str | None = None) -> Path:
    """
    Write index.html listing every sumvideo page in a directory, newest first.

    Args:
        directory: Directory containing sumvideo pages
        base_url: Public URL of the directory, used for og:url

    Returns:
        Path to the index file
    """
    pages = []
    for html_path in sorted(directory.glob('*.html')):
        if html_path.name == INDEX_FILENAME:
            continue
        info = read_page_info(html_path)
        if info is None:
            continue
        thumbnail = info['thumbnail']
        has_thumbnail = bool(thumbnail) and (directory / thumbnail).exists()
        if sync_tag_block(html_path, info['tags'], index_url(base_url)):
            logger.info(f"Updated tags shown on {html_path.name}")
        tag_links = [(slugify(tag), tag) for tag in info['tags'] if slugify(tag)]
        pages.append(dict(info, href=quote(info['filename']),
                          thumbnail_src=quote(thumbnail) if has_thumbnail else "",
                          tag_links=tag_links,
                          classes=' '.join(dict.fromkeys(f't-{slug}' for slug, _ in tag_links))))
    pages.sort(key=lambda page: (page['published'], page['filename']), reverse=True)
    tags = index_tags(pages)

    env = Environment(autoescape=True)
    html_content = env.from_string(INDEX_TEMPLATE).render(
        site_name=SITE_NAME,
        pages=pages,
        tags=tags,
        updated=datetime.now().astimezone().strftime("%Y-%m-%d"),
        page_url=public_url(base_url, INDEX_FILENAME) if base_url else "",
    )
    index_path = directory / INDEX_FILENAME
    index_path.write_text(html_content, encoding='utf-8')
    logger.info(f"Wrote index of {len(pages)} pages: {index_path}")
    return index_path

def get_default_output_dir() -> Path:
    """
    Determine the default output directory for videos.
    
    Checks for XDG_VIDEOS_DIR, then SUMVIDEO_DIR environment variables.
    If neither is set, creates a 'videos' directory in the current working directory.
    
    Returns:
        Path to the default output directory
    """
    # Check for XDG_VIDEOS_DIR
    xdg_videos_dir = os.environ.get('XDG_VIDEOS_DIR')
    if xdg_videos_dir:
        result = Path(xdg_videos_dir)
        result.mkdir(parents=True, exist_ok=True)
        return result
    
    # Check for SUMVIDEO_DIR
    sumvideo_dir = os.environ.get('SUMVIDEO_DIR')
    if sumvideo_dir:
        result = Path(sumvideo_dir)
        result.mkdir(parents=True, exist_ok=True)
        return result
    
    # Use current working directory with 'videos' subdirectory
    default_dir = Path.cwd() / 'videos'
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir

def get_base_url(output_dir: Path) -> str | None:
    """
    Get the public URL for output_dir from SUMVIDEO_BASE_URL.

    SUMVIDEO_BASE_URL is the URL where the default output directory is served,
    so it is ignored when writing anywhere else.

    Args:
        output_dir: Directory the HTML page is written to

    Returns:
        The base URL, or None if it is unset or does not apply to output_dir
    """
    base_url = os.environ.get('SUMVIDEO_BASE_URL')
    if not base_url:
        return None
    if output_dir.resolve() != get_default_output_dir().resolve():
        logger.info("Ignoring SUMVIDEO_BASE_URL: output is not going to the default directory")
        return None
    return base_url

def write_index(output_dir: Path) -> None:
    """
    Rebuild the index of pages in output_dir and report where it is.

    Args:
        output_dir: Directory containing sumvideo pages
    """
    base_url = get_base_url(output_dir)
    index_path = build_index(output_dir, base_url)
    print(f"Index created: {index_path}")
    if base_url:
        print(f"Index URL: {public_url(base_url, INDEX_FILENAME)}")

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Download a video and create an HTML description page.',
        epilog='''
Examples:
  sumvideo.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
  sumvideo.py --standalone https://twitter.com/username/status/123456789
  sumvideo.py -o ~/Videos -f webm https://vimeo.com/123456789
  sumvideo.py --index
        '''
    )
    parser.add_argument('url', nargs='?', help='URL of the video to download')
    parser.add_argument('-o', '--output-dir', default=None, 
                      help='Directory to save the video and HTML files')
    parser.add_argument('-f', '--format', default=DEFAULT_VIDEO_FORMAT, 
                      help=f'Video format to download ({", ".join(VIDEO_EXTENSIONS)})')
    parser.add_argument('--standalone', action='store_true', 
                      help='Create a standalone HTML file with embedded video and metadata')
    parser.add_argument('--keep-all', action='store_true', 
                      help='Keep all downloaded files (default is to clean up)')
    parser.add_argument('-v', '--verbose', action='store_true', 
                      help='Enable verbose logging')
    parser.add_argument('--cookies-from-browser',
                      help='Extract cookies from browser (chrome, firefox, safari, etc.)')
    parser.add_argument('--cookies',
                      help='Path to Netscape format cookie file')
    parser.add_argument('--style', default=DEFAULT_STYLE,
                      choices=list(STYLES.keys()),
                      help=f'Visual style for the HTML page (default: {DEFAULT_STYLE})')
    parser.add_argument('--tag', action='append', default=[], metavar='TAG',
                      help='Tag the page; repeat for more tags. Tags are stored as '
                           '<meta property="video:tag"> lines, which can be edited by hand')
    parser.add_argument('--index', action='store_true',
                      help=f'Write {INDEX_FILENAME} listing every page in the output directory '
                           '(after downloading, if a URL is given)')
    args = parser.parse_args()
    if not args.url and not args.index:
        parser.error('a video URL is required (or use --index)')
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Determine output directory
    output_dir = Path(args.output_dir) if args.output_dir else get_default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.url:
        write_index(output_dir)
        return
    
    # Download the video
    logger.info(f"Downloading video from {args.url}...")
    metadata = download_video(args.url, output_dir, args.format, args.cookies_from_browser,
                              args.cookies, keep_all=args.keep_all)
    
    if metadata is None:
        logger.error("Download failed. Exiting.")
        sys.exit(1)
    
    # Get the video title from metadata
    video_title = metadata.get('title', 'video')
    
    # Create a shorter filename using our helper function
    short_slug = generate_short_slug(video_title, metadata.get('upload_date'))
    new_video_filename = f"{short_slug}.{args.format}"
    
    # Define the path for the renamed video file
    new_video_path = output_dir / new_video_filename
    
    # Only ever use the file yt-dlp says it wrote. Guessing from the directory
    # once renamed another page's video in a shared archive.
    video_path = downloaded_file(metadata)
    if video_path is None:
        logger.error("yt-dlp did not report the file it downloaded; stopping rather than "
                     "guessing, so no existing video gets renamed")
        sys.exit(1)
    logger.debug(f"Downloaded file: {video_path}")

    # Rename files to use the slug if they're not already using it
    if video_path and video_path.name != new_video_filename:
        try:
            logger.debug(f"Renaming video file from {video_path} to {new_video_path}")
            
            # Get the base filename without extension before renaming
            original_base = video_path.stem
            
            # Rename video file
            video_path.rename(new_video_path)
            
            # Find and rename the JSON metadata file
            json_path = output_dir / f"{original_base}.info.json"
            if json_path.exists():
                new_json_path = output_dir / f"{short_slug}.info.json"
                logger.debug(f"Renaming JSON file from {json_path} to {new_json_path}")
                json_path.rename(new_json_path)
            
            # Find and rename thumbnail file based on yt-dlp's naming convention
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                thumb_path = output_dir / f"{original_base}{ext}"
                if thumb_path.exists():
                    new_thumb_path = output_dir / f"{short_slug}{ext}"
                    logger.debug(f"Renaming thumbnail from {thumb_path} to {new_thumb_path}")
                    thumb_path.rename(new_thumb_path)
            
            # Update the video path for HTML generation
            video_path = new_video_path
            
        except OSError as e:
            logger.error(f"Error renaming files: {e}")
            # If renaming failed, the original path is now invalid, so use the new path
            video_path = new_video_path if new_video_path.exists() else video_path
    
    # Normal pages link to the thumbnail file, so make it a JPEG for link previews
    thumbnail_path = find_thumbnail(output_dir, video_path.stem)
    if thumbnail_path and not args.standalone:
        thumbnail_path = ensure_jpeg_thumbnail(thumbnail_path)

    # Create the HTML description page
    logger.info("Creating HTML description page...")
    base_url = get_base_url(output_dir)
    tags = [tag.strip() for tag in args.tag if tag.strip()]
    html_path = create_html(metadata, str(video_path), str(output_dir), args.standalone, args.style,
                            base_url=base_url, tags=tags)
    html_path = Path(html_path)  # Convert back to Path object
    
    # Determine if we should clean up files (default is yes, unless --keep-all is specified)
    should_cleanup = not args.keep_all
    if should_cleanup:
        files_to_remove = []
        
        # In standalone mode, we can remove the video file because it's embedded in HTML
        if args.standalone and new_video_path.exists():
            files_to_remove.append(new_video_path)
        
        # JSON metadata file using the slugified name
        json_path = output_dir / f"{short_slug}.info.json"
        if json_path.exists():
            files_to_remove.append(json_path)
        
        # Thumbnails named after the video, or after the video id
        files_to_remove.extend(thumbnail_files(output_dir, short_slug))
        if 'id' in metadata:
            files_to_remove.extend(thumbnail_files(output_dir, str(metadata['id'])))
                    
        # Keep the HTML file we just created, and the thumbnail a normal page links to
        keep = {html_path} if args.standalone else {html_path, thumbnail_path}
        files_to_remove = [f for f in files_to_remove if f not in keep]
        files_to_remove = list(set(files_to_remove))  # Remove duplicates
        
        # Remove the files
        if files_to_remove:
            logger.info("Cleaning up downloaded files...")
            for file_path in files_to_remove:
                try:
                    file_path.unlink()
                    logger.info(f"Removed: {file_path.name}")
                except OSError as e:
                    logger.error(f"Failed to remove {file_path.name}: {e}")
    
    logger.info("Done!")
    if not (should_cleanup and args.standalone):
        logger.info(f"Video saved to: {video_path}")
    logger.info(f"HTML page saved to: {html_path}")
    
    # Print final status for user
    print(f"\nSuccessfully downloaded and processed: {video_title}")
    print(f"HTML page created: {html_path}")
    if base_url:
        print(f"Public URL: {public_url(base_url, html_path.name)}")
    
    if args.standalone:
        print("Created standalone HTML file with embedded video and metadata.")
        if should_cleanup:
            print("Original files have been removed automatically.")
            print("You can extract the video and JSON from the HTML page using the download buttons.")
        else:
            print("Original files kept (--keep-all).")
            print("You can open the HTML page in your browser to view the video and download the original files.")
    else:
        if should_cleanup:
            print("JSON metadata has been removed automatically; video and thumbnail are kept.")
            print("Use --keep-all to keep all downloaded files.")
        else:
            print("All original files kept (--keep-all).")
        print("You can open the HTML page in your browser to view the video and its metadata.")

    if args.index:
        write_index(output_dir)

if __name__ == "__main__":
    main()
