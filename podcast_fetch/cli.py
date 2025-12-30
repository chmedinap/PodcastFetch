"""
Command Line Interface for PodcastFetch.
"""

import argparse
import sys
import os
from pathlib import Path
import sqlite3

from podcast_fetch import config
from podcast_fetch import (
    collect_data,
    normalize_feed_url,
    get_apple_podcast_info,
    get_podcast_title,
    is_valid_database,
    get_db_connection,
    table_exists,
    summary_exists,
    add_podcast_image_url_to_summary,
    download_all_episodes,
    download_last_episode,
    show_podcast_summary,
    update_summary,
    clean_dataframe_for_sqlite,
    add_indexes_to_table,
)
from podcast_fetch.database.schema import create_summary_table_if_not_exists


def process_feeds_file(feeds_file='feeds.txt'):
    """Process all feeds from feeds.txt file."""
    feeds_path = Path(feeds_file)
    
    if not feeds_path.exists():
        print(f"❌ Error: {feeds_file} not found!")
        print(f"   Please create {feeds_file} and add your podcast feed URLs.")
        return False
    
    # Read feeds from file
    with open(feeds_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()]
    
    # Filter out comments and empty lines
    feeds = [line for line in lines if line and not line.startswith('#')]
    
    if not feeds:
        print(f"⚠️  No feeds found in {feeds_file}")
        print("   Add feed URLs (one per line) to process them.")
        return False
    
    print(f"📋 Found {len(feeds)} feed(s) to process\n")
    
    # Ensure database exists and is valid
    db_path = config.DB_PATH
    if os.path.exists(db_path):
        if not is_valid_database(db_path):
            print(f"⚠️  Database {db_path} is corrupted. Creating new database...")
            os.remove(db_path)
    
    # Connect to database
    with get_db_connection(db_path) as conn:
        # Ensure summary table has new columns
        add_podcast_image_url_to_summary(conn)
        
        # Process each feed
        for idx, feed_url in enumerate(feeds, 1):
            print(f"{'='*60}")
            print(f"Processing feed {idx}/{len(feeds)}: {feed_url}")
            print(f"{'='*60}")
            
            try:
                # Normalize feed URL (handle Apple Podcast links)
                normalized_url = normalize_feed_url(feed_url)
                
                # Collect data
                print("📥 Fetching podcast data...")
                df = collect_data(normalized_url)
                
                if df.empty:
                    print(f"⚠️  No episodes found in feed: {feed_url}")
                    continue
                
                # Get podcast title
                title = df['author'].iloc[0] if len(df) > 0 else 'unknown'
                print(f"📻 Podcast: {title}")
                print(f"📊 Episodes found: {len(df)}")
                
                # Extract RSS feed URL and podcast image URL
                rss_feed_url = df.attrs.get('rss_feed_url', None) if hasattr(df, 'attrs') else None
                podcast_image_url = df.attrs.get('podcast_image_url', None) if hasattr(df, 'attrs') else None
                
                if not rss_feed_url:
                    rss_feed_url = normalized_url
                
                # Check if podcast already exists
                if table_exists(conn, title):
                    print(f"ℹ️  Podcast '{title}' already exists. Updating...")
                else:
                    print(f"✨ Creating new podcast: '{title}'")
                
                # Save to database
                print("💾 Saving to database...")
                df_clean = clean_dataframe_for_sqlite(df)
                df_clean.to_sql(title, conn, if_exists='replace', index=False)
                add_indexes_to_table(conn, title)
                
                # Update summary
                update_summary(conn, title, podcast_image_url=podcast_image_url, rss_feed_url=rss_feed_url)
                
                print(f"✅ Successfully processed: {title}\n")
                
            except Exception as e:
                print(f"❌ Error processing feed '{feed_url}': {e}")
                print(f"   Skipping to next feed...\n")
                continue
    
    print(f"{'='*60}")
    print("✅ Feed processing complete!")
    print(f"{'='*60}")
    return True


def list_podcasts():
    """List all podcasts in the database."""
    db_path = config.DB_PATH
    
    if not os.path.exists(db_path):
        print("❌ Database not found. Process feeds first using: podcast-fetch process-feeds")
        return False
    
    if not is_valid_database(db_path):
        print("❌ Database is corrupted. Please recreate it.")
        return False
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        try:
            # Ensure summary table exists
            create_summary_table_if_not_exists(conn)
            
            # Get all tables (podcasts)
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'summary'
                ORDER BY name
            """)
            
            podcasts = cursor.fetchall()
            
            if not podcasts:
                print("📭 No podcasts found in database.")
                print("   Process feeds first using: podcast-fetch process-feeds")
                return False
            
            print(f"📻 Found {len(podcasts)} podcast(s):\n")
            
            for idx, (podcast_name,) in enumerate(podcasts, 1):
                # Get summary info
                try:
                    cursor.execute("SELECT num_episodes, num_episodes_downloaded FROM summary WHERE name = ?", (podcast_name,))
                    result = cursor.fetchone()
                    
                    if result:
                        total, downloaded = result
                        print(f"{idx}. {podcast_name}")
                        print(f"   Episodes: {downloaded}/{total} downloaded")
                    else:
                        print(f"{idx}. {podcast_name}")
                except sqlite3.Error:
                    # If summary query fails, just show the podcast name
                    print(f"{idx}. {podcast_name}")
                print()
            
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            return False


def show_status(podcast_name=None):
    """Show download status for podcast(s)."""
    db_path = config.DB_PATH
    
    if not os.path.exists(db_path):
        print("❌ Database not found. Process feeds first using: podcast-fetch process-feeds")
        return False
    
    with get_db_connection(db_path) as conn:
        try:
            if podcast_name:
                # Show status for specific podcast
                if not table_exists(conn, podcast_name):
                    print(f"❌ Podcast '{podcast_name}' not found in database.")
                    return False
                
                summary = show_podcast_summary(conn, [podcast_name])
                if summary:
                    print(f"\n📊 Summary for '{podcast_name}':")
                    print(f"   Episodes to download: {summary[podcast_name]}")
            else:
                # Show status for all podcasts
                # Get all podcast names from database
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'summary'
                    ORDER BY name
                """)
                all_podcasts = [row[0] for row in cursor.fetchall()]
                
                if not all_podcasts:
                    print("📭 No podcasts found in database.")
                    return False
                
                summary = show_podcast_summary(conn, all_podcasts)
                if summary:
                    print("\n📊 Download Status:")
                    for name, count in summary.items():
                        print(f"   {name}: {count} episode(s) to download")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


def download_episodes(podcast_name, last_only=False):
    """Download episodes for a podcast."""
    db_path = config.DB_PATH
    
    if not os.path.exists(db_path):
        print("❌ Database not found. Process feeds first using: podcast-fetch process-feeds")
        return False
    
    with get_db_connection(db_path) as conn:
        try:
            if not table_exists(conn, podcast_name):
                print(f"❌ Podcast '{podcast_name}' not found in database.")
                print("   Use 'podcast-fetch list' to see available podcasts.")
                return False
            
            if last_only:
                print(f"📥 Downloading last episode for '{podcast_name}'...")
                success = download_last_episode(conn, podcast_name)
            else:
                print(f"📥 Downloading all episodes for '{podcast_name}'...")
                successful, failed = download_all_episodes(conn, podcast_name)
                success = successful > 0
            
            if success:
                print("✅ Download complete!")
            else:
                print("⚠️  No episodes were downloaded.")
            
            return success
            
        except KeyboardInterrupt:
            print("\n⚠️  Download interrupted by user.")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


def add_feed(feed_url):
    """Add a single feed to feeds.txt and process it."""
    feeds_path = Path('feeds.txt')
    
    # Check if feed already exists
    if feeds_path.exists():
        with open(feeds_path, 'r', encoding='utf-8') as f:
            existing_feeds = [line.strip() for line in f.readlines()]
            if feed_url in existing_feeds:
                print(f"ℹ️  Feed already exists in feeds.txt")
                print("   Processing existing feed...")
            else:
                # Add to feeds.txt
                with open(feeds_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n{feed_url}\n")
                print(f"✅ Added feed to feeds.txt")
    
    # Process the feed
    return process_feeds_file('feeds.txt')


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='PodcastFetch - Download and manage podcast episodes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  podcast-fetch process-feeds              # Process all feeds from feeds.txt
  podcast-fetch list                       # List all podcasts
  podcast-fetch status                     # Show download status
  podcast-fetch download podcast_name      # Download all episodes
  podcast-fetch download-last podcast_name # Download last episode only
  podcast-fetch add <feed-url>             # Add and process a feed
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Process feeds command
    process_parser = subparsers.add_parser('process-feeds', help='Process all feeds from feeds.txt')
    process_parser.add_argument('--file', default='feeds.txt', help='Feeds file path (default: feeds.txt)')
    
    # List podcasts command
    subparsers.add_parser('list', help='List all podcasts in database')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show download status')
    status_parser.add_argument('podcast', nargs='?', help='Podcast name (optional, shows all if omitted)')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download all episodes for a podcast')
    download_parser.add_argument('podcast', help='Podcast name')
    
    # Download last command
    download_last_parser = subparsers.add_parser('download-last', help='Download only the last episode')
    download_last_parser.add_argument('podcast', help='Podcast name')
    
    # Add feed command
    add_parser = subparsers.add_parser('add', help='Add a feed URL and process it')
    add_parser.add_argument('feed_url', help='RSS feed URL or Apple Podcast link')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'process-feeds':
            success = process_feeds_file(args.file)
        elif args.command == 'list':
            success = list_podcasts()
        elif args.command == 'status':
            success = show_status(args.podcast)
        elif args.command == 'download':
            success = download_episodes(args.podcast, last_only=False)
        elif args.command == 'download-last':
            success = download_episodes(args.podcast, last_only=True)
        elif args.command == 'add':
            success = add_feed(args.feed_url)
        else:
            parser.print_help()
            return 1
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user.")
        return 130
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

