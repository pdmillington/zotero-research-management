#!/usr/bin/env python3
"""
Fix Missing Semantic Scholar IDs
---------------------------------
For papers that have citation data but no SS ID in Zotero Extra field.
Only processes papers missing IDs - much faster than full re-run.
"""

import time
import requests
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
    exit(1)


SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"


def get_api_headers():
    """Get headers with API key if available"""
    headers = {}
    try:
        from config import SEMANTIC_SCHOLAR_API_KEY
        if SEMANTIC_SCHOLAR_API_KEY:
            headers['x-api-key'] = SEMANTIC_SCHOLAR_API_KEY
    except (ImportError, AttributeError):
        pass
    return headers


def search_by_doi(doi):
    """Quick search by DOI only"""
    if not doi:
        return None
    
    url = f"{SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}"
    params = {'fields': 'paperId'}
    headers = get_api_headers()
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('paperId')
        elif response.status_code == 429:
            print("  Rate limited, waiting 30s...")
            time.sleep(30)
            return None
        else:
            return None
    except Exception:
        return None


def search_by_title(title, year=None):
    """Quick search by title only"""
    if not title:
        return None
    
    url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
    params = {
        'query': title,
        'limit': 1,
        'fields': 'paperId,title'
    }
    if year:
        params['year'] = str(year)
    
    headers = get_api_headers()
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            papers = data.get('data', [])
            if papers:
                # Basic title match
                found_title = papers[0].get('title', '').lower()
                query_title = title.lower()
                if query_title[:30] in found_title or found_title[:30] in query_title:
                    return papers[0].get('paperId')
            return None
        elif response.status_code == 429:
            print("  Rate limited, waiting 30s...")
            time.sleep(30)
            return None
        else:
            return None
    except Exception:
        return None


def parse_extra_field(extra_text):
    """Parse Semantic Scholar ID from Extra field"""
    if not extra_text:
        return None
    
    for line in extra_text.replace('\r\n', '\n').split('\n'):
        line = line.strip()
        if line.lower().startswith('semantic scholar id:'):
            ss_id = line.split(':', 1)[1].strip()
            return ss_id if ss_id else None
    
    return None


def update_zotero_extra_field(zot, item_key, ss_id, title):
    """Add SS ID to a single item's Extra field"""
    try:
        # Fetch item
        item = zot.item(item_key)
        
        # Get existing Extra field
        existing_extra = item['data'].get('extra', '').strip()
        
        # Check if SS ID already exists
        lines = existing_extra.split('\n') if existing_extra else []
        
        # Remove any old SS ID lines
        lines = [line for line in lines if not line.lower().startswith('semantic scholar id:')]
        
        # Add new SS ID line
        lines.append(f'Semantic Scholar ID: {ss_id}')
        
        # Update item
        item['data']['extra'] = '\n'.join(lines)
        zot.update_item(item)
        
        return True
    except Exception as e:
        print(f"  Error updating: {e}")
        return False


def find_missing_ids(csv_path):
    """Find papers missing SS IDs"""
    
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"ERROR: {csv_path} not found!")
        print("Run fetch_library_with_collections.py first")
        return None
    
    print(f"\nAnalyzing library: {len(df)} papers")
    
    if 'semantic_scholar_id' not in df.columns:
        print("  No semantic_scholar_id column found")
        print("  All papers need SS IDs")
        missing = df
    else:
        missing = df[df['semantic_scholar_id'].isna()].copy()
    
    print(f"  Papers missing SS IDs: {len(missing)}")
    
    return missing


def fix_missing_ids(dry_run=False):
    """Main function to fix missing SS IDs"""
    
    # Load library
    csv_path = f"{OUTPUT_DIR}/{DEFAULT_CSV}"
    
    missing = find_missing_ids(csv_path)
    
    if missing is None or len(missing) == 0:
        print("\n✓ All papers have Semantic Scholar IDs!")
        return
    
    print("\n" + "="*70)
    print("PAPERS MISSING SEMANTIC SCHOLAR IDs")
    print("="*70)
    
    # Show sample
    print("\nSample of papers that need IDs:")
    sample_cols = ['title', 'year', 'doi']
    available_cols = [c for c in sample_cols if c in missing.columns]
    print(missing[available_cols].head(10).to_string(index=False))
    
    if len(missing) > 10:
        print(f"... and {len(missing) - 10} more")
    
    print("\n" + "="*70)
    
    if dry_run:
        print("\nDRY RUN - no changes will be made")
        print("Run without --dry-run to actually fix these")
        return
    
    # Confirm
    response = input(f"\nFetch Semantic Scholar IDs for {len(missing)} papers? (y/n): ")
    
    if response.lower() != 'y':
        print("Cancelled")
        return
    
    # Initialize Zotero connection
    zot = zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)
    
    print("\nFetching Semantic Scholar IDs...")
    print("="*70 + "\n")
    
    found_count = 0
    not_found_count = 0
    updated_count = 0
    
    for idx, row in missing.iterrows():
        paper_num = idx + 1
        total = len(missing)
        
        title = row.get('title', '')
        doi = row.get('doi', '')
        year = row.get('year', '')
        key = row.get('key', '')
        
        print(f"[{paper_num}/{total}] {title[:55]}...")
        
        ss_id = None
        
        # Try DOI first
        if doi:
            ss_id = search_by_doi(doi)
            if ss_id:
                print(f"  ✓ Found via DOI: {ss_id}")
                found_count += 1
        
        # Fallback to title
        if not ss_id and title:
            time.sleep(3)  # Rate limiting
            ss_id = search_by_title(title, year)
            if ss_id:
                print(f"  ✓ Found via title: {ss_id}")
                found_count += 1
            else:
                print(f"  ✗ Not found")
                not_found_count += 1
        
        # Update Zotero if we found ID
        if ss_id:
            success = update_zotero_extra_field(zot, key, ss_id, title)
            if success:
                updated_count += 1
                print(f"  ✓ Updated Zotero Extra field")
            time.sleep(1)  # Rate limit for Zotero API
        
        # Rate limiting between papers
        if not ss_id and doi:
            time.sleep(3)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Papers processed: {len(missing)}")
    print(f"SS IDs found: {found_count}")
    print(f"Not found: {not_found_count}")
    print(f"Zotero updated: {updated_count}")
    print("="*70)
    
    if updated_count > 0:
        print("\n✓ Semantic Scholar IDs have been added to Zotero!")
        print("\nNext steps:")
        print("1. Run: python fetch_library_with_collections.py")
        print("2. Your CSV will now have all Semantic Scholar IDs")
        print("3. Discovery tools will now work for all papers")


def main():
    import sys
    
    dry_run = '--dry-run' in sys.argv
    
    print("="*70)
    print("FIX MISSING SEMANTIC SCHOLAR IDs")
    print("="*70)
    print("\nThis script will:")
    print("  1. Find papers without Semantic Scholar IDs")
    print("  2. Look them up on Semantic Scholar")
    print("  3. Add IDs to Zotero Extra field")
    print("\nNote: This does NOT update citation counts")
    print("      Run add_citations.py for that")
    print("="*70)
    
    fix_missing_ids(dry_run=dry_run)


if __name__ == '__main__':
    main()
