#!/usr/bin/env python3
"""
Fetch Zotero library via API and export to clean CSV
"""

import os
from pathlib import Path
import pandas as pd
from pyzotero import zotero

try:
    from config import (
        ZOTERO_LIBRARY_ID,
        ZOTERO_LIBRARY_TYPE, 
        ZOTERO_API_KEY,
        OUTPUT_DIR,
        DEFAULT_CSV
    )
except ImportError:
    print("ERROR: config.py not found!")
    print("Copy config_template.py to config.py and fill in your credentials")
    print("Get API key from: https://www.zotero.org/settings/keys")
    exit(1)


def fetch_zotero_library():
    """Fetch all items from Zotero library"""
    print(f"Connecting to Zotero library {ZOTERO_LIBRARY_ID}...")
    
    zot = zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)
    
    print("Fetching items...")
    items = zot.everything(zot.items())
    
    print(f"Fetched {len(items)} items")
    return items


def extract_useful_fields(items):
    """Extract only useful fields from Zotero items"""
    
    papers = []
    
    for item in items:
        data = item.get('data', {})
        
        # Skip non-paper items (notes, attachments, etc.)
        item_type = data.get('itemType', '')
        if item_type in ['note', 'attachment']:
            continue
        
        # Extract authors
        creators = data.get('creators', [])
        authors = []
        for c in creators:
            first = c.get('firstName', '')
            last = c.get('lastName', '')
            name = f"{first} {last}".strip() or c.get('name', '')
            if name:
                authors.append(name)
        
        # Extract tags
        tags = data.get('tags', [])
        tag_list = [t.get('tag', '') for t in tags]
        
        # Parse structured tags (score:5, priority:high, etc.)
        score = None
        quality = None
        status = None
        priority = None
        topics = []
        
        for tag in tag_list:
            if ':' in tag:
                key, value = tag.split(':', 1)
                if key == 'score':
                    try:
                        score = int(value)
                    except ValueError:
                        pass
                elif key == 'quality':
                    try:
                        quality = int(value)
                    except ValueError:
                        pass
                elif key == 'status':
                    status = value
                elif key == 'priority':
                    priority = value
                elif key == 'topic':
                    topics.append(value)
                else:
                    topics.append(tag)  # Keep the whole tag if unknown prefix
            else:
                topics.append(tag)
        
        # Build paper record
        paper = {
            'key': item.get('key', ''),
            'title': data.get('title', ''),
            'authors': '; '.join(authors),
            'year': data.get('date', '')[:4] if data.get('date') else '',
            'journal': data.get('publicationTitle', ''),
            'item_type': item_type,
            'doi': data.get('DOI', ''),
            'url': data.get('url', ''),
            'abstract': data.get('abstractNote', ''),
            'tags': '; '.join(tag_list),
            'topics': '; '.join(topics),
            'score': score,
            'quality': quality,
            'status': status,
            'priority': priority,
            'date_added': data.get('dateAdded', ''),
            'date_modified': data.get('dateModified', ''),
        }
        
        papers.append(paper)
    
    return papers


def save_to_csv(papers, output_path):
    """Save papers to CSV"""
    
    df = pd.DataFrame(papers)
    
    # Reorder columns for readability
    column_order = [
        'title', 'authors', 'year', 'journal', 'item_type',
        'score', 'quality', 'status', 'priority',
        'topics', 'tags',
        'doi', 'url', 'abstract',
        'key', 'date_added', 'date_modified'
    ]
    
    # Only keep columns that exist
    column_order = [col for col in column_order if col in df.columns]
    df = df[column_order]
    
    # Save
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} papers to {output_path}")
    
    return df


def print_summary(df):
    """Print summary statistics"""
    
    print("\n" + "="*60)
    print("LIBRARY SUMMARY")
    print("="*60)
    
    print(f"\nTotal papers: {len(df)}")
    
    # Item types
    print("\nItem types:")
    print(df['item_type'].value_counts())
    
    # Scored papers
    scored = df['score'].notna().sum()
    print(f"\nScored papers: {scored} / {len(df)} ({scored/len(df)*100:.1f}%)")
    
    if scored > 0:
        print("\nScore distribution:")
        print(df['score'].value_counts().sort_index())
    
    # Status
    if df['status'].notna().sum() > 0:
        print("\nRead status:")
        print(df['status'].value_counts())
    
    # Priority
    if df['priority'].notna().sum() > 0:
        print("\nPriority:")
        print(df['priority'].value_counts())
    
    # Years
    print("\nPapers by year (recent):")
    year_counts = df[df['year'] != '']['year'].value_counts().head(10)
    print(year_counts.sort_index(ascending=False))
    
    print("\n" + "="*60)


def main():
    """Main function"""
    
    # Create output directory
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, DEFAULT_CSV)
    
    # Fetch library
    items = fetch_zotero_library()
    
    # Extract fields
    papers = extract_useful_fields(items)
    
    # Save to CSV
    df = save_to_csv(papers, output_path)
    
    # Print summary
    print_summary(df)
    
    print(f"\n✓ Library exported successfully!")
    print(f"  File: {output_path}")
    print(f"\nNext steps:")
    print(f"  1. Open {output_path} in Excel/LibreOffice")
    print(f"  2. Add scores using Zotero tags (e.g., 'score:5', 'priority:high')")
    print(f"  3. Re-run this script to update")


if __name__ == '__main__':
    main()
