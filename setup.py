"""
Setup script for PodcastFetch package.
"""

from setuptools import setup, find_packages

setup(
    name='podcast-fetch',
    version='1.0.0',
    description='A podcast RSS feed parser and downloader',
    packages=find_packages(),
    install_requires=[
        'pandas',
        'numpy',
        'feedparser',
        'requests',
        'mutagen',  # For ID3 tag management
        'tqdm',  # For progress bars
    ],
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            'podcast-fetch=podcast_fetch.cli:main',
        ],
    },
)




