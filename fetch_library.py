#!/usr/bin/env python3
"""
Fetch Zotero library via API and export to clean CSV
"""

import os
from pathlib import Path
import pandas as pd
from pyzotero import zotero
from collections import defaultdict

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
    
    print("Fetching collections...")
    collections = zot.collections()
    
    print(f"Fetched {len(items)} items and {len(collections)} collections.")
    return items, collections, zot

def build_collections_map(collections):
    """"Build a map of collection IDs to names with full paths"""
    collection_map = {}
    
    for col in collections:
        col_id = col['key']
        col_data = col['data']
        collection_map[col_id] = {
            'name': col_data.get('name', ''),
            'parent': col_data.get('parentCollection', None)
            }

    def get_full_path(col_id):
        path = []
        current = col_id
        
        while current:
            col = collection_map.get(current)
            if not col:
                break
            path.insert(0, col['name'])
            current = col['parent']
            
        return '>'.join(path)
    
    for col_id in collection_map:
        collection_map[col_id]['full_path'] = get_full_path(col_id)
    
    return collection_map

def parse_extra_field(extra_text):
    """
    Parse Semantic Scholar ID from Extra field
    Returns SS ID or None
    """
    if not extra_text:
        return None
    
    for line in extra_text.split('\n'):
        line = line.strip()
        if line.startswith('Semantic Scholar ID:'):
            # Extract ID after the colon
            ss_id = line.split(':', 1)[1].strip()
            return ss_id if ss_id else None
    
    return None

def get_item_collections(item, collection_map):
    """Get all collections that an item belongs to"""
    try:
        collection_keys = item.get('data', {}).get('collections',[])
        
        collection_paths = []
        for col_key in collection_keys:
            if col_key in collection_map:
                collection_paths.append(collection_map[col_key]['full_path'])
        
        return sorted(collection_paths)
    
    except Exception as e:
        print(f"  Warning: could not fetch collections for item {item}.\n  Error: {e}")
        return []

def extract_useful_fields(items, collections, zot):
    """Extract only useful fields from Zotero items"""
    
    collection_map = build_collections_map(collections)
    
    # Get all unique collections for the columns
    all_collection_paths = sorted(set(
        col['full_path'] for col in collection_map.values()
        ))
    
    print(f"\nFound {len(all_collection_paths)} unique collections")
    print("Processing items")
    
    papers = []
    
    for idx, item in enumerate(items, 1):
        if idx % 50 == 0:
            print(f" Processed {idx}/{len(items)} items...")
            
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
        
        # Extract Extra field
        extra = data.get('extra', '')
        semantic_scholar_id = parse_extra_field(extra)
        
        # Parse structured tags (score:5, priority:high, etc.)
        score = None
        quality = None
        status = None
        priority = None
        citations = None
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
                    priority = value.strip()
                elif key == 'citations':
                    try:
                        citations = int(value)
                    except ValueError:
                        pass
                elif key == 'topic':
                    topics.append(value)
                else:
                    topics.append(tag)  # Keep the whole tag if unknown prefix
            else:
                topics.append(tag)
        
        item_collections = get_item_collections(item, collection_map)
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
            'citations': citations,
            'semantic_scholar_id': semantic_scholar_id,
            'date_added': data.get('dateAdded', ''),
            'date_modified': data.get('dateModified', ''),
            'num_collections': len(item_collections),
        }
        
        # List collection columns and fill with 1s and 0s
        for col_path in all_collection_paths:
            col_name = f"in_{col_path}".replace('>', '_').replace(' ','_').replace('-', '_')
            paper[col_name] = 1 if col_path in item_collections else 0
        
        paper['collections'] = ';'.join(item_collections)
        
        papers.append(paper)
        
    print(f"  Processed {len(items)} items in total")
    
    return papers, all_collection_paths


def save_to_csv(papers, output_path, all_collection_paths):
    """Save papers to CSV with collections as separate columns"""
    
    df = pd.DataFrame(papers)
    
    # Reorder columns for readability
    base_columns = [
        'title', 'authors', 'year', 'journal', 'item_type',
        'score', 'quality', 'status', 'priority','citations',
        'topics', 'tags', 'semantic_scholar_id',
        'num_collections', 'collections',
    ]
    
    # Add collection membership columns
    collection_columns = [
        f"in_{col_path}".replace(' > ', '_').replace(' ', '_').replace('-', '_')
        for col_path in all_collection_paths
    ]
    
    # Then other metadata
    metadata_columns = [
        'doi', 'url', 'abstract',
        'key', 'date_added', 'date_modified'
    ]
    
    # Only keep columns that exist
    column_order = base_columns + collection_columns + metadata_columns
    
    # Only keep columns that exist
    column_order = [col for col in column_order if col in df.columns]
    df = df[column_order]
    
    # Save
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} papers to {output_path}")
    
    return df


def print_summary(df, all_collection_paths):
    """Print summary statistics"""
    
    print("\n" + "="*60)
    print("LIBRARY SUMMARY")
    print("="*60)
    
    print(f"\nTotal papers: {len(df)}")
    
    # Item types
    print("\nItem types:")
    print(df['item_type'].value_counts())
    
    # Collections
    print(f"\nTotal collections: {len(all_collection_paths)}")
    if len(all_collection_paths) > 0:
        print("\nTop collections by number of items:")
        collection_counts = df['num_collections'].value_counts()
        
        # Show distribution
        print(f"  Papers in 0 collections: {df[df['num_collections'] == 0].shape[0]}")
        print(f"  Papers in 1 collection: {df[df['num_collections'] == 1].shape[0]}")
        print(f"  Papers in 2+ collections: {df[df['num_collections'] >= 2].shape[0]}")
        print(f"  Max collections per paper: {df['num_collections'].max()}")
    
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
    items, collections, zot = fetch_zotero_library()
    
    # Extract fields
    papers, all_collection_paths = extract_useful_fields(items, collections, zot)
    
    # Save to CSV
    df = save_to_csv(papers, output_path, all_collection_paths)
    
    # Print summary
    print_summary(df, all_collection_paths)
    
    print("\n✓ Library exported successfully!")
    print(f"  File: {output_path}")

    print(f"\nCollection columns:")
    print(f"  - 'collections': Semicolon-separated list of all collections")
    print(f"  - 'num_collections': Count of collections")
    print(f"  - 'in_[Collection_Name]': Binary (1/0) for each collection")
    
    print(f"\nFiltering examples in Excel:")
    print(f"  - Filter 'in_Reading_Queue' = 1 to see only those papers")
    print(f"  - Filter 'in_Current_Research' = 1 AND 'status' = 'unread'")
    print(f"  - Sort by 'num_collections' to find papers in many collections")
    
    print(f"\nNext steps:")
    print(f"  1. Open {output_path} in Excel/LibreOffice")
    print(f"  2. Use AutoFilter on collection columns")
    print(f"  3. Add scores using Zotero tags (e.g., 'score:5', 'priority:high')")
    print(f"  4. Re-run this script to update")

if __name__ == '__main__':
    main()
