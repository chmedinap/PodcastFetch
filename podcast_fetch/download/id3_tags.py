"""
ID3 tag management for podcast episode MP3 files.
"""

import logging
import traceback
from pathlib import Path
from typing import Optional
from podcast_fetch import config

# Set up logging
logger = logging.getLogger(__name__)

try:
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, TPOS, TCON, COMM, APIC
    from mutagen.mp3 import MP3
    from mutagen import File
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logger.warning("mutagen library not available. ID3 tag updates will be skipped.")
    logger.warning("Install with: pip install mutagen")


def update_mp3_id3_tags(
    file_path: Path,
    title: str,
    artist: str,
    album: str,
    year: Optional[int] = None,
    track: Optional[int] = None,
    disc_number: Optional[int] = None,
    comment: Optional[str] = None,
    cover_image_path: Optional[Path] = None,
    genre: str = "Podcast"
) -> bool:
    """
    Update ID3 tags for an MP3 file.
    
    Parameters:
    file_path: Path to the MP3 file
    title: Episode title
    artist: Podcast name (author_raw)
    album: Podcast name (author_raw)
    year: Year of release
    track: Episode number
    disc_number: Season number
    comment: Episode summary
    cover_image_path: Path to cover image (podcast or episode image)
    genre: Genre (default: "Podcast")
    
    Returns:
    bool: True if successful, False otherwise
    """
    if not MUTAGEN_AVAILABLE:
        logger.warning("mutagen not available, skipping ID3 tag update")
        return False
    
    if not file_path.exists():
        logger.error(f"File does not exist: {file_path}")
        return False
    
    try:
        # Load the MP3 file
        audio_file = File(str(file_path))
        
        # If the file doesn't have ID3 tags, add them
        if audio_file.tags is None:
            audio_file.add_tags()
        
        # Update title
        if title:
            audio_file.tags['TIT2'] = TIT2(encoding=3, text=title)
        
        # Update artist (author_raw)
        if artist:
            audio_file.tags['TPE1'] = TPE1(encoding=3, text=artist)
        
        # Update album (author_raw)
        if album:
            audio_file.tags['TALB'] = TALB(encoding=3, text=album)
        
        # Update year
        if year:
            audio_file.tags['TDRC'] = TDRC(encoding=3, text=str(year))
        
        # Update track (episode number)
        if track is not None:
            audio_file.tags['TRCK'] = TRCK(encoding=3, text=str(track))
        
        # Update disc number (season number)
        if disc_number is not None:
            audio_file.tags['TPOS'] = TPOS(encoding=3, text=str(disc_number))
        
        # Update genre
        if genre:
            audio_file.tags['TCON'] = TCON(encoding=3, text=genre)
        
        # Update comment (summary)
        if comment:
            # Remove existing COMM frames and add new one
            audio_file.tags.delall('COMM')
            audio_file.tags['COMM'] = COMM(encoding=3, lang='eng', desc='', text=comment)
        
        # Update cover image
        if cover_image_path and cover_image_path.exists():
            try:
                # Remove existing APIC frames
                audio_file.tags.delall('APIC')
                
                # Read the image file
                with open(cover_image_path, 'rb') as img_file:
                    image_data = img_file.read()
                
                # Determine MIME type from file extension
                ext = cover_image_path.suffix.lower()
                mime_type = 'image/jpeg'  # default
                if ext == '.png':
                    mime_type = 'image/png'
                elif ext == '.jpg' or ext == '.jpeg':
                    mime_type = 'image/jpeg'
                elif ext == '.gif':
                    mime_type = 'image/gif'
                elif ext == '.webp':
                    mime_type = 'image/webp'
                
                # Add cover image
                audio_file.tags['APIC'] = APIC(
                    encoding=3,
                    mime=mime_type,
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=image_data
                )
                logger.info(f"Successfully added cover image to ID3 tags: {cover_image_path} (MIME: {mime_type})")
            except Exception as e:
                logger.warning(f"Failed to add cover image to ID3 tags: {e}")
                logger.debug(traceback.format_exc())
        else:
            if cover_image_path:
                logger.warning(f"Cover image path specified but file does not exist: {cover_image_path}")
            else:
                logger.debug("No cover image found for this episode")
        
        # Save the changes
        audio_file.save()
        logger.info(f"Successfully updated ID3 tags for {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update ID3 tags for {file_path}: {e}")
        logger.debug(traceback.format_exc())
        return False


def update_episode_id3_tags_from_db(
    conn,
    podcast_name: str,
    episode_id: str,
    file_path: Path,
    episode_folder: Path
) -> bool:
    """
    Update ID3 tags for an episode MP3 file using data from the database.
    
    Parameters:
    conn: SQLite connection
    podcast_name: Name of the podcast (table name)
    episode_id: Episode ID
    file_path: Path to the MP3 file
    episode_folder: Path to the episode folder (for finding images)
    
    Returns:
    bool: True if successful, False otherwise
    """
    try:
        cursor = conn.cursor()
        
        # Get episode data from database
        cursor.execute(f"""
            SELECT 
                title,
                author_raw,
                episode_number,
                season_number,
                summary,
                published,
                episode_image_url
            FROM {podcast_name}
            WHERE id = ?
        """, (episode_id,))
        
        result = cursor.fetchone()
        if not result:
            logger.warning(f"Episode {episode_id} not found in database")
            return False
        
        title, author_raw, episode_number, season_number, summary, published, episode_image_url = result
        
        # Extract year from published date
        year = None
        if published:
            try:
                from datetime import datetime
                # Try to parse the published date
                if isinstance(published, str):
                    # Try common date formats
                    for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%a, %d %b %Y %H:%M:%S %z']:
                        try:
                            dt = datetime.strptime(published, fmt)
                            year = dt.year
                            break
                        except ValueError:
                            continue
                    # If no format worked, try to extract year from string
                    if year is None:
                        import re
                        year_match = re.search(r'\d{4}', published)
                        if year_match:
                            year = int(year_match.group())
                elif hasattr(published, 'year'):
                    year = published.year
            except Exception as e:
                logger.debug(f"Could not extract year from published date: {e}")
        
        # Find cover image (prefer episode image, fallback to podcast image)
        cover_image_path = None
        
        # First, try episode image in episode folder
        # Search for any file starting with "episode_image" in the episode folder
        try:
            episode_image_files = list(episode_folder.glob("episode_image.*"))
            if episode_image_files:
                # Get the first matching file (should only be one)
                cover_image_path = episode_image_files[0]
                logger.debug(f"Found episode image: {cover_image_path}")
        except Exception as e:
            logger.debug(f"Error searching for episode image: {e}")
        
        # If no episode image, try podcast image in parent folder
        if not cover_image_path:
            try:
                # Go up two levels: episode_folder -> year -> podcast
                podcast_base_folder = episode_folder.parent.parent
                podcast_image_files = list(podcast_base_folder.glob("podcast_image.*"))
                if podcast_image_files:
                    # Get the first matching file (should only be one)
                    cover_image_path = podcast_image_files[0]
                    logger.debug(f"Found podcast image: {cover_image_path}")
            except Exception as e:
                logger.debug(f"Error searching for podcast image: {e}")
        
        # Convert episode_number and season_number to integers if they're strings
        track = None
        if episode_number is not None:
            try:
                track = int(float(str(episode_number)))
            except (ValueError, TypeError):
                pass
        
        disc_number = None
        if season_number is not None:
            try:
                disc_number = int(float(str(season_number)))
            except (ValueError, TypeError):
                pass
        
        # Update ID3 tags
        return update_mp3_id3_tags(
            file_path=file_path,
            title=title or "",
            artist=author_raw or "",
            album=author_raw or "",
            year=year,
            track=track,
            disc_number=disc_number,
            comment=summary or "",
            cover_image_path=cover_image_path,
            genre="Podcast"
        )
        
    except Exception as e:
        logger.error(f"Failed to update ID3 tags from database: {e}")
        logger.debug(traceback.format_exc())
        return False

