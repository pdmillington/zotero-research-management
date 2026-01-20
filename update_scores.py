#!/usr/bin/env python3
"""
Update Zotero items with scores from CSV
Reads scored_papers.csv and updates tags in Zotero
"""

import pandas as pd
from pyzotero import zotero

try:
    from config import (
        ZOTERO_LIBRARY_ID,
        ZOTERO_LIBRARY_TYPE,
        ZOTERO_API_KEY,
        OUTPUT_DIR,
        SCORED_CSV
    )
except ImportError:
    print("ERROR: config.py not found!")
    exit(1)


def update_item_tags(zot, item_key, score=None, quality=None, status=None, priority=None):
    """Update tags for a single item"""
    
    # Fetch current item
    item = zot.item(item_key)
    current_tags = item['data'].get('tags', [])
    
    # Remove old score/quality/status/priority tags
    new_tags = []
    for tag in current_tags:
        tag_text = tag.get('tag', '')
        if not any(tag_text.startswith(prefix) for prefix in ['score:', 'quality:', 'status:', 'priority:']):
            new_tags.append(tag)
    
    # Add new tags
    if score is not None:
        new_tags.append({'tag': f'score:{int(score)}'})
    if quality is not None:
        new_tags.append({'tag': f'quality:{int(quality)}'})
    if status:
        new_tags.append({'tag': f'status:{status}'})
    if priority:
        new_tags.append({'tag': f'priority:{priority}'})
    
    # Update item
    item['data']['tags'] = new_tags
    zot.update_item(item)


def main():
    """Main function"""
    
    csv_path = f"{OUTPUT_DIR}/{SCORED_CSV}"
    
    # Load CSV
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"ERROR: {csv_path} not found!")
        print("Run fetch_library.py first, then add scores in the CSV")
        return
    
    # Connect to Zotero
    print("Connecting to Zotero...")
    zot = zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)
    
    # Filter to items with scores
    to_update = df[df['score'].notna() | df['quality'].notna() | df['status'].notna() | df['priority'].notna()]
    
    print(f"Updating {len(to_update)} items...")
    
    for idx, row in to_update.iterrows():
        item_key = row['key']
        score = row['score'] if pd.notna(row['score']) else None
        quality = row['quality'] if pd.notna(row['quality']) else None
        status = row['status'] if pd.notna(row['status']) else None
        priority = row['priority'] if pd.notna(row['priority']) else None
        
        try:
            update_item_tags(zot, item_key, score, quality, status, priority)
            print(f"✓ Updated: {row['title'][:50]}")
        except Exception as e:
            print(f"✗ Failed: {row['title'][:50]} - {e}")
    
    print(f"\n✓ Updated {len(to_update)} items in Zotero")


if __name__ == '__main__':
    main()
