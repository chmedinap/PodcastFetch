"""
Download utility functions.
"""

import sqlite3
import logging
import traceback
import pandas as pd
from typing import List, Dict
from podcast_fetch.database.queries import table_exists
from podcast_fetch import config

# Set up logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    
    # Add file handler if configured
    if config.LOG_FILE:
        file_handler = logging.FileHandler(config.LOG_FILE)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def sanitize_filename(filename: str) -> str:
    """
    Remove or replace invalid characters from filename.
    
    Parameters:
    filename: Original filename
    
    Returns:
    Sanitized filename safe for filesystem use
    """
    # Remove invalid characters for filenames
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    # Limit filename length
    if len(filename) > config.MAX_FILENAME_LENGTH:
        filename = filename[:config.MAX_FILENAME_LENGTH]
    return filename


def show_podcast_summary(conn: sqlite3.Connection, podcast_names: List[str]) -> Dict[str, int]:
    """
    Show a summary of episodes to download for multiple podcasts.
    
    Parameters:
    conn: SQLite connection object
    podcast_names: List of podcast names (normalized table names)
    
    Returns:
    Dictionary with podcast names as keys and episode counts as values
    """
    summary = {}
    print(f"\n{'='*70}")
    print(f"📊 PODCAST DOWNLOAD SUMMARY")
    print(f"{'='*70}")
    
    total_episodes = 0
    for podcast_name in podcast_names:
        if not table_exists(conn, podcast_name):
            print(f"  ⚠️  '{podcast_name}': Table does not exist")
            summary[podcast_name] = 0
            continue
        
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM {podcast_name} 
                WHERE status = 'not downloaded'
            """)
            count = cursor.fetchone()[0]
            summary[podcast_name] = count
            total_episodes += count
        except sqlite3.Error as e:
            logger.error(f"Database error getting episode count for '{podcast_name}': {e}")
            logger.debug(traceback.format_exc())
            print(f"  ⚠️  '{podcast_name}': Error reading database")
            summary[podcast_name] = 0
        
        if count > 0:
            print(f"  📻 '{podcast_name}': {count} episode(s) to download")
        else:
            print(f"  ✓ '{podcast_name}': All episodes already downloaded")
    
    print(f"{'='*70}")
    print(f"📊 TOTAL: {total_episodes} episode(s) across {len(podcast_names)} podcast(s)")
    print(f"{'='*70}\n")
    
    return summary


def parse_episode_date(conn: sqlite3.Connection, podcast_name: str, episode_id: str, published_date: str = None) -> pd.Timestamp:
    """
    Parse episode publication date from various formats.
    
    Parameters:
    conn: SQLite connection object
    podcast_name: Name of the podcast (table name)
    episode_id: ID of the episode
    published_date: Published date string (optional)
    
    Returns:
    pd.Timestamp object representing the episode date, or current timestamp if parsing fails
    """
    try:
        # Try to parse the published date
        if published_date:
            # Try parsing as ISO format string first
            try:
                episode_date = pd.to_datetime(published_date)
                return episode_date
            except (ValueError, TypeError) as e:
                # If that fails, try parsing the published_parsed if available
                logger.debug(f"Failed to parse published_date '{published_date}': {e}. Trying published_parsed.")
                try:
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT published_parsed FROM {podcast_name} WHERE id = ?", (episode_id,))
                    parsed_result = cursor.fetchone()
                    if parsed_result and parsed_result[0]:
                        try:
                            episode_date = pd.to_datetime(parsed_result[0])
                            return episode_date
                        except (ValueError, TypeError) as e2:
                            logger.debug(f"Failed to parse published_parsed '{parsed_result[0]}': {e2}")
                except sqlite3.Error as db_error:
                    logger.warning(f"Database error reading published_parsed for episode {episode_id}: {db_error}")
                    logger.debug(traceback.format_exc())
    except sqlite3.Error as e:
        logger.error(f"Database error in parse_episode_date for episode {episode_id}: {e}")
        logger.debug(traceback.format_exc())
    except Exception as e:
        logger.warning(f"Unexpected error in parse_episode_date for episode {episode_id}: {e}")
        logger.debug(traceback.format_exc())
    
    # Fallback to current timestamp
    return pd.Timestamp.now()


