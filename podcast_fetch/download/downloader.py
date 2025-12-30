"""
Main download functions for podcast episodes.
"""

import sqlite3
import time
import logging
import traceback
import requests
import pandas as pd
from pathlib import Path
from typing import Tuple
from podcast_fetch import config
from podcast_fetch.database.queries import table_exists, validate_and_quote_table_name
from podcast_fetch.database.schema import add_download_columns_to_table, update_download_info
from podcast_fetch.download.utils import sanitize_filename, parse_episode_date
from podcast_fetch.download.metadata import update_summary
from podcast_fetch.data.collection import get_episode_xml_from_rss
from podcast_fetch.download.id3_tags import update_episode_id3_tags_from_db
from podcast_fetch.download.id3_tags import update_episode_id3_tags_from_db

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


def _download_image(image_url: str, image_path: Path) -> bool:
    """
    Download an image from a URL and save it to a file path.
    
    Parameters:
    image_url: URL of the image to download
    image_path: Path where the image should be saved
    
    Returns:
    True if download successful, False otherwise
    """
    try:
        logger.debug(f"Downloading image from {image_url} to {image_path}")
        response = requests.get(image_url, stream=True, timeout=config.DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        
        # Determine file extension from URL or Content-Type
        content_type = response.headers.get('Content-Type', '')
        if 'image/jpeg' in content_type or 'image/jpg' in content_type:
            ext = '.jpg'
        elif 'image/png' in content_type:
            ext = '.png'
        elif 'image/gif' in content_type:
            ext = '.gif'
        elif 'image/webp' in content_type:
            ext = '.webp'
        else:
            # Try to get extension from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(image_url)
            path = parsed_url.path.lower()
            if path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                ext = path[path.rfind('.'):]
            else:
                ext = '.jpg'  # Default to jpg
        
        # Update path with correct extension
        if not str(image_path).lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            image_path = image_path.with_suffix(ext)
        
        # Save the image
        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=config.CHUNK_SIZE):
                f.write(chunk)
        
        logger.info(f"Successfully downloaded image to {image_path}")
        return True
        
    except requests.RequestException as e:
        logger.warning(f"Failed to download image from {image_url}: {e}")
        return False
    except OSError as e:
        logger.error(f"File system error saving image to {image_path}: {e}")
        logger.debug(traceback.format_exc())
        return False
    except Exception as e:
        logger.error(f"Unexpected error downloading image: {e}")
        logger.debug(traceback.format_exc())
        return False


def _download_with_retry(episode_url: str, file_path: Path) -> None:
    """
    Download a file with retry logic for transient failures.
    
    Parameters:
    episode_url: URL of the episode to download
    file_path: Path where the file should be saved
    
    Raises:
    requests.RequestException: For network-related errors
    OSError: For file system errors
    """
    max_retries = config.MAX_RETRIES
    retry_delay = config.RETRY_DELAY_BASE
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Download attempt {attempt + 1}/{max_retries} for {episode_url}")
            response = requests.get(episode_url, stream=True, timeout=config.DOWNLOAD_TIMEOUT)
            response.raise_for_status()
            
            # Save the file
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=config.CHUNK_SIZE):
                    f.write(chunk)
            
            logger.info(f"Successfully downloaded {episode_url} to {file_path}")
            return
            
        except requests.Timeout as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Timeout downloading {episode_url} (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, config.RETRY_DELAY_MAX)
            else:
                logger.error(f"Timeout downloading {episode_url} after {max_retries} attempts")
                raise
                
        except requests.ConnectionError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Connection error downloading {episode_url} (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, config.RETRY_DELAY_MAX)
            else:
                logger.error(f"Connection error downloading {episode_url} after {max_retries} attempts")
                raise
                
        except requests.HTTPError as e:
            # HTTP errors (4xx, 5xx) are usually not transient, don't retry
            logger.error(f"HTTP error downloading {episode_url}: {e}")
            raise
            
        except OSError as e:
            # File system errors are usually not transient, don't retry
            logger.error(f"File system error saving {file_path}: {e}")
            logger.debug(traceback.format_exc())
            raise
            
        except requests.RequestException as e:
            # Other request exceptions - retry if it might be transient
            if attempt < max_retries - 1:
                logger.warning(
                    f"Request error downloading {episode_url} (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {retry_delay} seconds..."
                )
                logger.debug(traceback.format_exc())
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, config.RETRY_DELAY_MAX)
            else:
                logger.error(f"Request error downloading {episode_url} after {max_retries} attempts: {e}")
                logger.debug(traceback.format_exc())
                raise


def download_all_episodes(
    conn: sqlite3.Connection,
    podcast_name: str,
    downloads_folder: str = None,
    delay_seconds: int = None
) -> Tuple[int, int]:
    """
    Download all episodes of a podcast that haven't been downloaded yet.
    Organizes files in: downloads/podcast_title/year/date - episode_title/Episode_Title - podcast_name.mp3
    Adds a delay between downloads to avoid overwhelming the server.
    
    Parameters:
    conn: SQLite connection object
    podcast_name: Name of the podcast (normalized table name)
    downloads_folder: Folder to save downloads (default: config.DOWNLOADS_FOLDER)
    delay_seconds: Delay in seconds between downloads (default: config.DEFAULT_DELAY_SECONDS)
    
    Returns:
    Tuple of (successful_downloads, total_episodes)
    """
    if downloads_folder is None:
        downloads_folder = config.DOWNLOADS_FOLDER
    if delay_seconds is None:
        delay_seconds = config.DEFAULT_DELAY_SECONDS
    
    # Create downloads folder if it doesn't exist
    try:
        Path(downloads_folder).mkdir(exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create downloads folder '{downloads_folder}': {e}")
        logger.debug(traceback.format_exc())
        print(f"Error: Failed to create downloads folder: {e}")
        return (0, 0)
    
    # Check if table exists
    if not table_exists(conn, podcast_name):
        print(f"Table '{podcast_name}' does not exist in database.")
        return (0, 0)
    
    # Ensure the download columns exist in the table
    add_download_columns_to_table(conn, podcast_name)
    
    # Get all episodes that haven't been downloaded, ordered by published date (newest first)
    cursor = conn.cursor()
    safe_table_name = validate_and_quote_table_name(podcast_name)
    cursor.execute(f"""
        SELECT title, link_direct, published, id, episode_image_url, link
        FROM {safe_table_name} 
        WHERE status = 'not downloaded'
        ORDER BY published DESC
    """)
    
    episodes = cursor.fetchall()
    
    if not episodes:
        print(f"No episodes to download for '{podcast_name}'. All episodes may already be downloaded.")
        return (0, 0)
    
    total_episodes = len(episodes)
    
    # Show episode count and ask for confirmation
    print(f"\n{'='*60}")
    print(f"📊 Download Summary for '{podcast_name}'")
    print(f"{'='*60}")
    print(f"Number of episodes to download: {total_episodes}")
    print(f"Delay between downloads: {delay_seconds} seconds")
    print(f"{'='*60}\n")
    
    # Ask for user confirmation
    while True:
        user_input = input(f"Do you want to download {total_episodes} episode(s) for '{podcast_name}'? (yes/no): ").strip().lower()
        if user_input in ['yes', 'y']:
            print(f"\n✓ Confirmed. Starting downloads...\n")
            break
        elif user_input in ['no', 'n']:
            print(f"\n✗ Download cancelled by user.\n")
            return (0, total_episodes)
        else:
            print("Please enter 'yes' or 'no'.")
    
    successful_downloads = 0
    failed_downloads = 0
    
    # Batch transaction configuration
    batch_size = config.BATCH_COMMIT_SIZE
    pending_updates = []  # Track episodes that need database updates
    
    print(f"Starting downloads with {delay_seconds} second delay between episodes...")
    print(f"Using batch transactions: committing every {batch_size} episodes\n")
    
    # Begin transaction for batch processing
    cursor.execute("BEGIN TRANSACTION")
    
    # Download podcast image once (if available)
    podcast_base_folder = Path(downloads_folder) / podcast_name
    podcast_image_downloaded = False
    
    # Try to get podcast image URL from summary table or from feed metadata
    # We'll need to store this when collecting data - for now, try to get from first episode
    # or we can add it to summary table later
    podcast_image_url = None
    try:
        # Check if we stored it in summary (we'll add this column later)
        # For now, we'll get it from the feed when processing
        pass
    except sqlite3.Error:
        pass
    
    # Get RSS feed URL from summary table for metadata extraction
    rss_feed_url = None
    try:
        cursor.execute("""
            SELECT rss_feed_url FROM summary WHERE name = ?
        """, (podcast_name,))
        result = cursor.fetchone()
        if result and result[0]:
            rss_feed_url = result[0]
            logger.info(f"Found RSS feed URL in summary: {rss_feed_url}")
        else:
            logger.debug(f"RSS feed URL not found in summary for {podcast_name}")
    except sqlite3.Error as e:
        logger.debug(f"Could not get RSS feed URL from summary (column may not exist): {e}")
    
    for idx, episode in enumerate(episodes, 1):
        episode_title, episode_url, published_date, episode_id, episode_image_url, episode_link = episode
        
        print(f"[{idx}/{total_episodes}] Processing: {episode_title}")
        
        if not episode_url:
            print(f"  ⚠️  No download URL found for episode '{episode_title}'. Skipping.")
            failed_downloads += 1
            continue
        
        # Parse and format the date using helper function
        episode_date = parse_episode_date(conn, podcast_name, episode_id, published_date)
        
        # Extract year and format date
        year = episode_date.year
        date_str = episode_date.strftime('%Y-%m-%d')
        
        # Sanitize the episode title for folder name
        safe_episode_title = sanitize_filename(episode_title)
        
        # Create folder structure: downloads/podcast_name/year/date - episode_title/
        episode_folder = Path(downloads_folder) / podcast_name / str(year) / f"{date_str} - {safe_episode_title}"
        try:
            episode_folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create folder '{episode_folder}': {e}")
            logger.debug(traceback.format_exc())
            print(f"  ✗ Error creating folder: {e}")
            failed_downloads += 1
            continue
        
        # Ensure podcast base folder exists for podcast image
        try:
            podcast_base_folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Failed to create podcast base folder: {e}")
        
        # Base filename (without extension) for all episode files
        base_filename = f"{safe_episode_title} - {podcast_name}"
        
        # File will be saved as Episode_Title - podcast_name.mp3
        file_path = episode_folder / f"{base_filename}.mp3"
        
        # Check if file already exists
        if file_path.exists():
            print(f"  ✓ File already exists: {file_path}")
            # Update ID3 tags even if file already exists (in case metadata changed)
            try:
                if update_episode_id3_tags_from_db(conn, podcast_name, episode_id, file_path, episode_folder):
                    print(f"  🏷️  ID3 tags updated")
            except Exception as e:
                logger.debug(f"Error updating ID3 tags for existing file: {e}")
            # Update status even if file exists (no commit yet - batch transaction)
            cursor.execute(f"UPDATE {safe_table_name} SET status = 'downloaded' WHERE id = ?", (episode_id,))
            # Update download info fields (no auto commit - batch transaction)
            update_download_info(conn, podcast_name, episode_id, file_path, auto_commit=False)
            successful_downloads += 1
            pending_updates.append(('success', idx))
            
            # Commit batch if we've reached the batch size
            if len(pending_updates) >= batch_size:
                conn.commit()
                print(f"  💾 Committed batch of {len(pending_updates)} updates to database")
                pending_updates = []
                # Begin new transaction
                cursor.execute("BEGIN TRANSACTION")
            
            # Add delay before next episode (except for the last one)
            if idx < total_episodes:
                print(f"  ⏳ Waiting {delay_seconds} seconds before next episode...\n")
                time.sleep(delay_seconds)
            continue
        
        try:
            print(f"  📥 Downloading from: {episode_url}")
            print(f"  💾 Saving to: {file_path}")
            
            # Download the file with retry logic
            _download_with_retry(episode_url, file_path)
            
            print(f"  ✓ Downloaded successfully!")
            
            # Download episode image FIRST (before updating ID3 tags, so the image is available)
            # Image will be saved with same base name as MP3 (extension added by _download_image)
            if episode_image_url and episode_image_url.strip():
                episode_image_path = episode_folder / base_filename
                if _download_image(episode_image_url, episode_image_path):
                    print(f"  🖼️  Episode image downloaded: {episode_image_path}")
                else:
                    logger.warning(f"Failed to download episode image from {episode_image_url}")
            
            # Update ID3 tags with episode metadata from database (after image is downloaded)
            try:
                if update_episode_id3_tags_from_db(conn, podcast_name, episode_id, file_path, episode_folder):
                    print(f"  🏷️  ID3 tags updated successfully")
                else:
                    logger.warning(f"Failed to update ID3 tags for {file_path}")
            except Exception as e:
                logger.warning(f"Error updating ID3 tags: {e}")
                logger.debug(traceback.format_exc())
                # Don't fail the download if ID3 tag update fails
            
            # Save episode metadata XML (original RSS entry) for archival
            # Try to get RSS feed URL from summary table if not already retrieved
            if not rss_feed_url:
                try:
                    # Try to get RSS feed URL from summary (we'll store it there)
                    cursor.execute("""
                        SELECT rss_feed_url FROM summary WHERE name = ? LIMIT 1
                    """, (podcast_name,))
                    result = cursor.fetchone()
                    if result and result[0]:
                        rss_feed_url = result[0]
                        logger.info(f"Retrieved RSS feed URL from summary: {rss_feed_url}")
                    elif episode_link:
                        # Fallback: try to construct RSS URL from episode link domain
                        from urllib.parse import urlparse
                        parsed = urlparse(episode_link)
                        # Common RSS feed patterns
                        possible_rss_urls = [
                            f"{parsed.scheme}://{parsed.netloc}/feed",
                            f"{parsed.scheme}://{parsed.netloc}/rss",
                            f"{parsed.scheme}://{parsed.netloc}/podcast.xml",
                            f"{parsed.scheme}://{parsed.netloc}/feed.xml",
                        ]
                        # Try the first one as fallback
                        rss_feed_url = possible_rss_urls[0]
                        logger.warning(f"RSS feed URL not in summary, using fallback: {rss_feed_url}")
                except sqlite3.Error as e:
                    logger.warning(f"Could not get RSS feed URL from summary: {e}")
            
            # Extract and save episode metadata XML if RSS feed URL is available
            if rss_feed_url:
                try:
                    logger.debug(f"Attempting to extract XML metadata for episode {episode_id} from {rss_feed_url}")
                    episode_xml = get_episode_xml_from_rss(rss_feed_url, episode_id, episode_title, episode_link)
                    if episode_xml:
                        # XML file uses same base name as MP3
                        metadata_path = episode_folder / f"{base_filename}.xml"
                        with open(metadata_path, 'w', encoding='utf-8') as f:
                            # Write XML declaration and format the XML
                            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                            f.write('<rss version="2.0">\n')
                            f.write('  <channel>\n')
                            # Indent the item XML properly
                            lines = episode_xml.split('\n')
                            for line in lines:
                                if line.strip():
                                    f.write('    ' + line + '\n')
                            f.write('  </channel>\n')
                            f.write('</rss>\n')
                        print(f"  📄 Episode metadata XML saved: {metadata_path}")
                        logger.info(f"Successfully saved episode metadata XML to {metadata_path}")
                    else:
                        logger.warning(f"Could not extract XML metadata for episode {episode_id} (title: {episode_title})")
                        print(f"  ⚠️  Could not extract XML metadata for this episode")
                except Exception as e:
                    logger.error(f"Failed to save episode metadata XML: {e}")
                    logger.debug(traceback.format_exc())
                    print(f"  ⚠️  Error saving episode metadata XML: {e}")
            else:
                logger.warning(f"RSS feed URL not available for {podcast_name}, skipping metadata XML save")
                print(f"  ⚠️  RSS feed URL not available, skipping metadata XML save")
            
            # Download podcast image once (if not already downloaded and URL available)
            if not podcast_image_downloaded:
                # Try to get podcast image URL from summary table
                # We'll need to store it there when collecting data
                try:
                    cursor.execute("""
                        SELECT podcast_image_url FROM summary WHERE name = ?
                    """, (podcast_name,))
                    result = cursor.fetchone()
                    if result and result[0]:
                        podcast_image_url = result[0]
                        podcast_image_path = podcast_base_folder / "podcast_image"
                        if _download_image(podcast_image_url, podcast_image_path):
                            print(f"  🖼️  Podcast image downloaded: {podcast_image_path}")
                            podcast_image_downloaded = True
                        else:
                            logger.warning(f"Failed to download podcast image from {podcast_image_url}")
                            podcast_image_downloaded = True  # Mark as attempted
                    else:
                        podcast_image_downloaded = True  # No image URL available
                except sqlite3.Error as e:
                    logger.debug(f"Could not get podcast image URL from summary: {e}")
                    podcast_image_downloaded = True  # Mark as attempted to avoid repeated checks
            
            # Update status in database (no commit yet - batch transaction)
            try:
                cursor.execute(f"UPDATE {safe_table_name} SET status = 'downloaded' WHERE id = ?", (episode_id,))
                # Update download info fields (Saved_Path, Size, File_name) - no auto commit
                update_download_info(conn, podcast_name, episode_id, file_path, auto_commit=False)
            except sqlite3.Error as db_error:
                logger.error(f"Database error updating episode {episode_id}: {db_error}")
                logger.debug(traceback.format_exc())
                # Rollback and re-raise to handle at outer level
                conn.rollback()
                cursor.execute("BEGIN TRANSACTION")
                raise
            
            successful_downloads += 1
            pending_updates.append(('success', idx))
            
            # Commit batch if we've reached the batch size
            if len(pending_updates) >= batch_size:
                try:
                    conn.commit()
                    print(f"  💾 Committed batch of {len(pending_updates)} updates to database")
                    pending_updates = []
                    # Begin new transaction
                    cursor.execute("BEGIN TRANSACTION")
                except sqlite3.Error as db_error:
                    logger.error(f"Database error committing batch: {db_error}")
                    logger.debug(traceback.format_exc())
                    conn.rollback()
                    cursor.execute("BEGIN TRANSACTION")
                    pending_updates = []
            
            # Add delay before next episode (except for the last one)
            if idx < total_episodes:
                print(f"  ⏳ Waiting {delay_seconds} seconds before next episode...\n")
                time.sleep(delay_seconds)
            
        except requests.RequestException as e:
            print(f"  ✗ Network error downloading episode: {e}")
            logger.error(f"Network error downloading episode '{episode_title}': {e}")
            logger.debug(traceback.format_exc())
            failed_downloads += 1
            # Rollback current transaction on error, then begin new one
            try:
                conn.rollback()
                cursor.execute("BEGIN TRANSACTION")
            except sqlite3.Error as db_error:
                logger.error(f"Database error during rollback: {db_error}")
                logger.debug(traceback.format_exc())
            pending_updates = []
            # Still add delay even on failure
            if idx < total_episodes:
                print(f"  ⏳ Waiting {delay_seconds} seconds before next episode...\n")
                time.sleep(delay_seconds)
                
        except OSError as e:
            print(f"  ✗ File system error downloading episode: {e}")
            logger.error(f"File system error downloading episode '{episode_title}': {e}")
            logger.debug(traceback.format_exc())
            failed_downloads += 1
            # Rollback current transaction on error, then begin new one
            try:
                conn.rollback()
                cursor.execute("BEGIN TRANSACTION")
            except sqlite3.Error as db_error:
                logger.error(f"Database error during rollback: {db_error}")
                logger.debug(traceback.format_exc())
            pending_updates = []
            # Still add delay even on failure
            if idx < total_episodes:
                print(f"  ⏳ Waiting {delay_seconds} seconds before next episode...\n")
                time.sleep(delay_seconds)
                
        except sqlite3.Error as e:
            print(f"  ✗ Database error: {e}")
            logger.error(f"Database error processing episode '{episode_title}': {e}")
            logger.debug(traceback.format_exc())
            failed_downloads += 1
            # Rollback current transaction on error, then begin new one
            try:
                conn.rollback()
                cursor.execute("BEGIN TRANSACTION")
            except sqlite3.Error as db_error:
                logger.error(f"Database error during rollback: {db_error}")
                logger.debug(traceback.format_exc())
            pending_updates = []
            # Still add delay even on failure
            if idx < total_episodes:
                print(f"  ⏳ Waiting {delay_seconds} seconds before next episode...\n")
                time.sleep(delay_seconds)
    
    # Commit any remaining pending updates
    if pending_updates:
        conn.commit()
        print(f"  💾 Committed final batch of {len(pending_updates)} updates to database")
    
    print(f"\n{'='*60}")
    print(f"Download complete for '{podcast_name}':")
    print(f"  ✓ Successful: {successful_downloads}")
    print(f"  ✗ Failed: {failed_downloads}")
    print(f"  📊 Total: {total_episodes}")
    print(f"{'='*60}\n")
    
    # Update summary once at the end of all downloads (optimization: was called after each episode)
    if successful_downloads > 0 or failed_downloads > 0:
        print("📊 Updating summary statistics...")
        update_summary(conn, podcast_name)
    
    return (successful_downloads, total_episodes)


def download_last_episode(
    conn: sqlite3.Connection,
    podcast_name: str,
    downloads_folder: str = None
) -> bool:
    """
    Download the last (most recent) episode of a podcast that hasn't been downloaded yet.
    
    Parameters:
    conn: SQLite connection object
    podcast_name: Name of the podcast (normalized table name)
    downloads_folder: Folder to save downloads (default: config.DOWNLOADS_FOLDER)
    
    Returns:
    True if download successful, False otherwise
    """
    if downloads_folder is None:
        downloads_folder = config.DOWNLOADS_FOLDER
    
    # Get all episodes and download only the first one
    try:
        Path(downloads_folder).mkdir(exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create downloads folder '{downloads_folder}': {e}")
        logger.debug(traceback.format_exc())
        print(f"Error: Failed to create downloads folder: {e}")
        return False
    
    if not table_exists(conn, podcast_name):
        print(f"Table '{podcast_name}' does not exist in database.")
        return False
    
    cursor = conn.cursor()
    safe_table_name = validate_and_quote_table_name(podcast_name)
    cursor.execute(f"""
        SELECT title, link_direct, published, id 
        FROM {safe_table_name} 
        WHERE status = 'not downloaded'
        ORDER BY published DESC
        LIMIT 1
    """)
    
    episode = cursor.fetchone()
    
    if not episode:
        print(f"No episodes to download for '{podcast_name}'. All episodes may already be downloaded.")
        return False
    
    episode_title, episode_url, published_date, episode_id = episode
    
    if not episode_url:
        print(f"No download URL found for episode '{episode_title}'.")
        return False
    
    # Parse and format the date using helper function
    episode_date = parse_episode_date(conn, podcast_name, episode_id, published_date)
    
    year = episode_date.year
    date_str = episode_date.strftime('%Y-%m-%d')
    safe_episode_title = sanitize_filename(episode_title)
    podcast_folder = Path(downloads_folder) / podcast_name / str(year) / f"{date_str} - {safe_episode_title}"
    try:
        podcast_folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create folder '{podcast_folder}': {e}")
        logger.debug(traceback.format_exc())
        print(f"Error creating folder: {e}")
        return False
    file_path = podcast_folder / f"{safe_episode_title} - {podcast_name}.mp3"
    
    if file_path.exists():
        print(f"File already exists: {file_path}")
        # Update ID3 tags even if file already exists (in case metadata changed)
        try:
            if update_episode_id3_tags_from_db(conn, podcast_name, episode_id, file_path, podcast_folder):
                print(f"  🏷️  ID3 tags updated")
        except Exception as e:
            logger.debug(f"Error updating ID3 tags for existing file: {e}")
        cursor.execute(f"UPDATE {safe_table_name} SET status = 'downloaded' WHERE id = ?", (episode_id,))
        conn.commit()
        update_download_info(conn, podcast_name, episode_id, file_path)
        update_summary(conn, podcast_name)
        return True
    
    try:
        print(f"Downloading: {episode_title}")
        _download_with_retry(episode_url, file_path)
        print(f"Downloaded successfully: {file_path}")
        
        # Update ID3 tags with episode metadata from database
        try:
            if update_episode_id3_tags_from_db(conn, podcast_name, episode_id, file_path, podcast_folder):
                print(f"  🏷️  ID3 tags updated successfully")
        except Exception as e:
            logger.warning(f"Error updating ID3 tags: {e}")
            logger.debug(traceback.format_exc())
        
        try:
            cursor.execute(f"UPDATE {safe_table_name} SET status = 'downloaded' WHERE id = ?", (episode_id,))
            conn.commit()
            update_download_info(conn, podcast_name, episode_id, file_path)
            update_summary(conn, podcast_name)
        except sqlite3.Error as db_error:
            logger.error(f"Database error updating episode {episode_id}: {db_error}")
            logger.debug(traceback.format_exc())
            conn.rollback()
            return False
            
        return True
        
    except requests.RequestException as e:
        print(f"Network error downloading episode: {e}")
        logger.error(f"Network error downloading episode '{episode_title}': {e}")
        logger.debug(traceback.format_exc())
        return False
        
    except OSError as e:
        print(f"File system error downloading episode: {e}")
        logger.error(f"File system error downloading episode '{episode_title}': {e}")
        logger.debug(traceback.format_exc())
        return False
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        logger.error(f"Database error processing episode '{episode_title}': {e}")
        logger.debug(traceback.format_exc())
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return False


