"""
OxData - External Database Loader
=================================
Downloads database from external storage on each request.
Uses session-level caching to avoid repeated downloads.
"""

import os
import sys
import sqlite3
import shutil
import requests
from pathlib import Path

# Google Drive file ID - hardcoded for simplicity
DEFAULT_DRIVE_ID = "1XAKL7BQjux7rGv665rxiffhnzgtuIXM5"

BASE_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "project_1" / "oxdata.db"


def get_db_path() -> Path:
    """Get database path - download if needed."""
    return ensure_database()


def download_from_google_drive(file_id: str, dest_path: Path) -> bool:
    """Download file from Google Drive."""
    try:
        url = f"https://docs.google.com/uc?export=download&id={file_id}"
        
        print(f"Downloading from Google Drive: {file_id}...")
        session = requests.Session()
        
        response = session.get(url, stream=True, timeout=120)
        
        # Check if we got HTML instead of file
        if not response.content.startswith(b'SQLite'):
            # Try with confirm token
            content = response.text
            if 'confirm=' in content:
                import re
                match = re.search(r'confirm=([a-zA-Z0-9_-]+)', content)
                if match:
                    confirm_token = match.group(1)
                    url = f"https://docs.google.com/uc?export=download&id={file_id}&confirm={confirm_token}"
                    response = session.get(url, stream=True, timeout=120)
        
        # Verify it's a SQLite file
        if not response.content.startswith(b'SQLite'):
            print(f"ERROR: Not a SQLite file. Got {len(response.content)} bytes")
            return False
        
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
        
        print(f"Downloaded to {dest_path}")
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False


def ensure_database(db_path: Path = None) -> Path:
    """Ensure database exists - download on each call."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    # Check if valid database exists
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path), timeout=5)
            conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchall()
            conn.close()
            return db_path
        except:
            # Invalid database, remove and re-download
            try:
                db_path.unlink()
            except:
                pass
    
    # Get DB source - prioritize secrets, then env, then default
    db_source = None
    
    # Try Streamlit secrets first
    try:
        import streamlit as st
        db_source = st.secrets.get('DB_SOURCE', '')
        if not db_source:
            db_source = st.secrets.get('db_source', '')
    except:
        pass
    
    # Try environment variable
    if not db_source:
        db_source = os.environ.get('DB_SOURCE', '')
        if not db_source:
            db_source = os.environ.get('db_source', '')
    
    # Extract file ID from various formats
    file_id = None
    if db_source:
        if db_source.startswith('drive:'):
            file_id = db_source.replace('drive:', '').strip()
        elif len(db_source) == 33:  # Raw file ID
            file_id = db_source.strip()
        elif 'docs.google.com' in db_source or 'drive.google.com' in db_source:
            # Extract ID from URL
            import re
            match = re.search(r'/d/([a-zA-Z0-9_-]+)', db_source)
            if match:
                file_id = match.group(1)
    
    # Use default if not found
    if not file_id:
        file_id = DEFAULT_DRIVE_ID
    
    print(f"Downloading database (file_id: {file_id})...")
    
    if download_from_google_drive(file_id, db_path):
        return db_path
    
    return None


# For testing
if __name__ == '__main__':
    db = ensure_database()
    if db:
        print(f"Database ready: {db}")
        conn = sqlite3.connect(str(db))
        print(f"Tables: {[t[0] for t in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()]}")
        conn.close()
    else:
        print("Failed to get database")