"""
PodcastFetch - A podcast RSS feed parser and downloader.

This package provides functionality to:
- Parse RSS feeds and extract podcast episode information
- Store episode data in SQLite database
- Download podcast episodes with organized file structure
- Generate summary statistics
"""

__version__ = '1.0.0'

# Import config
from podcast_fetch import config

# Import data modules
from podcast_fetch.data.collection import (
    normalize, 
    collect_data, 
    get_rss_from_apple_podcast, 
    normalize_feed_url,
    get_podcast_title,
    get_apple_podcast_info,
    get_episode_xml_from_rss
)
from podcast_fetch.data.summary import summarise_podcasts

# Import database modules
from podcast_fetch.database.connection import (
    is_valid_database,
    get_db_connection,
    clean_dataframe_for_sqlite
)
from podcast_fetch.database.queries import (
    table_exists,
    summary_exists,
    has_downloaded_episodes,
    verify_downloaded_files_exist
)
from podcast_fetch.database.schema import (
    add_author_raw_column_to_table,
    update_all_tables_with_author_raw_column,
    add_episode_metadata_columns_to_table,
    update_all_tables_with_episode_metadata_columns,
    add_podcast_image_url_to_summary,
    add_download_columns_to_table,
    update_download_info,
    update_all_tables_with_download_columns,
    add_indexes_to_table,
    update_all_tables_with_indexes,
    explain_query_plan
)

# Import download modules
from podcast_fetch.download.utils import sanitize_filename, show_podcast_summary, parse_episode_date
from podcast_fetch.download.downloader import download_all_episodes, download_last_episode
from podcast_fetch.download.metadata import update_summary
from podcast_fetch.download.id3_tags import update_mp3_id3_tags, update_episode_id3_tags_from_db

__all__ = [
    # Config
    'config',
    # Data functions
    'normalize',
    'collect_data',
    'summarise_podcasts',
    'get_rss_from_apple_podcast',
    'normalize_feed_url',
    'get_podcast_title',
    'get_apple_podcast_info',
    'get_episode_xml_from_rss',
    # Database functions
    'is_valid_database',
    'get_db_connection',
    'clean_dataframe_for_sqlite',
    'table_exists',
    'summary_exists',
    'has_downloaded_episodes',
    'verify_downloaded_files_exist',
    'add_author_raw_column_to_table',
    'update_all_tables_with_author_raw_column',
    'add_episode_metadata_columns_to_table',
    'update_all_tables_with_episode_metadata_columns',
    'add_podcast_image_url_to_summary',
    'add_download_columns_to_table',
    'update_download_info',
    'update_all_tables_with_download_columns',
    'add_indexes_to_table',
    'update_all_tables_with_indexes',
    'explain_query_plan',
    # Download functions
    'sanitize_filename',
    'show_podcast_summary',
    'parse_episode_date',
    'download_all_episodes',
    'download_last_episode',
    'update_summary',
    'update_mp3_id3_tags',
    'update_episode_id3_tags_from_db',
]

