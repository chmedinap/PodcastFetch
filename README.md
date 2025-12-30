# PodcastFetch

A powerful Python application for downloading, organizing, and managing podcast episodes from RSS feeds. PodcastFetch automatically extracts metadata, organizes files, and updates MP3 ID3 tags with complete episode information.

## Features

- 📻 **RSS Feed Support**: Works with any RSS feed URL
- 🍎 **Apple Podcast Integration**: Automatically converts Apple Podcast links to RSS feeds
- 💾 **SQLite Database**: Stores all episode metadata in a local database
- 📥 **Automatic Downloads**: Download all episodes or just the latest
- 🏷️ **ID3 Tag Management**: Automatically updates MP3 tags with episode metadata
- 🖼️ **Image Handling**: Downloads and embeds podcast/episode cover art
- 📊 **Statistics**: Track download progress and podcast statistics
- 📁 **Organized Storage**: Episodes organized by podcast, year, and date
- 📄 **Metadata Archive**: Saves original RSS XML metadata for each episode

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Install Dependencies

```bash
# Clone or download the repository
cd PodcastFetch

# Install the package and dependencies
pip install -e .
```

This will install:
- pandas
- numpy
- feedparser
- requests
- mutagen (for ID3 tag management)

## Quick Start

### 1. Prepare Your Feed List

Create a file named `feeds.txt` in the project root directory. Add one RSS feed URL or Apple Podcast link per line:

```
https://feeds.example.com/podcast.rss
https://podcasts.apple.com/us/podcast/example-podcast/id123456789
https://another-podcast.com/feed.xml
```

**Note**: You can mix RSS feed URLs and Apple Podcast links. The application will automatically detect and convert Apple Podcast links.

See `feeds.txt` for detailed instructions and examples.

### 2. Process Your Feeds

```bash
podcast-fetch process-feeds
```

This will:
- Read all feeds from `feeds.txt`
- Automatically detect and convert Apple Podcast links to RSS feeds
- Extract episode metadata from each feed
- Store all information in a SQLite database (`podcast_data.db`)

### 3. List Your Podcasts

```bash
podcast-fetch list
```

This shows all podcasts in your database with download statistics.

### 4. Download Episodes

```bash
# Download all episodes for a podcast
podcast-fetch download podcast_name

# Or download only the latest episode
podcast-fetch download-last podcast_name
```

## Usage Guide

### Command Line Interface

PodcastFetch provides a simple command-line interface for all operations:

#### Process Feeds

```bash
# Process all feeds from feeds.txt
podcast-fetch process-feeds

# Or specify a custom feeds file
podcast-fetch process-feeds --file my-feeds.txt
```

This command:
- Reads URLs from `feeds.txt`
- Automatically detects Apple Podcast links and converts them to RSS feeds
- Extracts episode metadata from each feed
- Stores all information in a SQLite database (`podcast_data.db`)

#### List Podcasts

```bash
podcast-fetch list
```

Shows all podcasts in your database with download statistics.

#### Check Status

```bash
# Show status for all podcasts
podcast-fetch status

# Show status for a specific podcast
podcast-fetch status podcast_name
```

#### Download Episodes

```bash
# Download all episodes for a podcast
podcast-fetch download podcast_name

# Download only the latest episode
podcast-fetch download-last podcast_name
```

The download process will:
- Show you how many episodes will be downloaded
- Ask for confirmation before starting
- Download episodes with a delay between each (default: 5 seconds)
- Update ID3 tags automatically
- Download episode and podcast images

#### Add a Single Feed

```bash
podcast-fetch add https://feeds.example.com/podcast.rss
```

This adds the feed to `feeds.txt` and processes it immediately.

### Getting Help

```bash
podcast-fetch --help
podcast-fetch <command> --help
```

### File Organization

Episodes are organized in the following structure:

```
downloads/
  └── podcast_name/
      └── 2024/
          └── 2024-01-15 - Episode Title/
              ├── Episode Title - podcast_name.mp3
              ├── episode_image.jpg (if available)
              └── episode_metadata.xml (original RSS entry)
```

### ID3 Tags

Each downloaded MP3 file automatically includes:

- **Title**: Episode title
- **Artist**: Podcast name (original, before normalization)
- **Album**: Podcast name (same as Artist)
- **Year**: Publication year
- **Track**: Episode number (if available)
- **Disc**: Season number (if available)
- **Comment**: Episode summary/description
- **Cover Art**: Episode image (if available) or podcast cover art
- **Genre**: "Podcast"

### Viewing Statistics

```bash
# Show download status for all podcasts
podcast-fetch status

# Show status for a specific podcast
podcast-fetch status podcast_name
```

## Configuration

You can customize the application by editing `podcast_fetch/config.py`:

```python
# Download settings
DOWNLOADS_FOLDER = 'downloads'  # Where to save episodes
DEFAULT_DELAY_SECONDS = 5        # Delay between downloads
DOWNLOAD_TIMEOUT = 30            # Download timeout in seconds

# Database settings
DB_PATH = 'podcast_data.db'      # Database file location
DB_TIMEOUT = 30.0                # Database timeout

# Retry settings
MAX_RETRIES = 3                  # Retry attempts for failed downloads
RETRY_DELAY_BASE = 1             # Base delay for retries
RETRY_DELAY_MAX = 60             # Maximum delay for retries
```

## Common Tasks

### Adding a New Podcast

1. Add the RSS feed URL or Apple Podcast link to `feeds.txt`
2. Run the feed processing cell in the notebook
3. The new podcast will be added to the database

### Re-downloading Episodes

If you need to re-download episodes (e.g., if files were deleted):

1. The application will detect missing files
2. You can choose to re-download when processing feeds
3. Or manually delete the episode record from the database

### Updating Episode Metadata

If you've updated your database with new episode information:

1. The ID3 tags will be automatically updated when you re-download
2. Simply run `podcast-fetch download podcast_name` again to update tags

## Troubleshooting

### "mutagen library not available" Warning

If you see this warning, install mutagen:
```bash
pip install mutagen
```

### Episodes Not Downloading

- Check your internet connection
- Verify the RSS feed URL is correct
- Check the logs for error messages
- Ensure the downloads folder is writable

### ID3 Tags Not Updating

- Make sure mutagen is installed
- Check that the MP3 file exists and is writable
- Review the logs for specific error messages

### Database Errors

- Ensure you have write permissions in the project directory
- Check that the database file isn't locked by another process
- Try restarting the notebook kernel

## File Structure

```
PodcastFetch/
├── README.md                 # This file
├── ARCHITECTURE.md           # Technical documentation
├── feeds.txt                 # Your podcast feed list
├── podcast_data.db           # SQLite database (created automatically)
├── downloads/                # Downloaded episodes (created automatically)
├── setup.py                  # Package setup
└── podcast_fetch/            # Main package
    ├── __init__.py
    ├── cli.py                # Command-line interface
    ├── config.py             # Configuration settings
    ├── data/                 # Data collection modules
    │   ├── collection.py     # RSS feed parsing
    │   └── summary.py        # Statistics generation
    ├── database/             # Database modules
    │   ├── connection.py     # Database connections
    │   ├── queries.py        # Query utilities
    │   └── schema.py         # Schema management
    └── download/              # Download modules
        ├── downloader.py     # Main download functions
        ├── id3_tags.py       # ID3 tag management
        ├── metadata.py       # Metadata updates
        └── utils.py          # Utility functions
```

**Note**: The `notebook.ipynb` file is available for developers who want to use PodcastFetch programmatically or for advanced use cases. Most users should use the command-line interface.

## Tips

1. **Backup Your Database**: The database file (`podcast_data.db`) contains all your podcast metadata. Keep it backed up.

2. **Organize Your Feeds**: Keep `feeds.txt` organized with comments:
   ```
   # Technology Podcasts
   https://tech-podcast.com/feed
   
   # News Podcasts
   https://news-podcast.com/feed
   ```

3. **Check Download Space**: Large podcasts can take up significant disk space. Monitor your `downloads/` folder.

4. **Use Delays**: The default delay between downloads (5 seconds) helps avoid overwhelming servers. Adjust in `config.py` if needed.

## Support

For technical details and architecture information, see [ARCHITECTURE.md](ARCHITECTURE.md).

## License

This project is provided as-is for personal use.
