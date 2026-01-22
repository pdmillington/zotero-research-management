#!/usr/bin/env python3
"""
Add citation counts to your Zotero library using Semantic Scholar API
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


# Semantic Scholar API - no key needed for basic use
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_KEY = "6lKUUKO1zC1fjmDipQxQxqWegXC9SbRar1KVXVC8"


def search_semantic_scholar_by_doi(doi):
    """
    Search Semantic Scholar by DOI
    Returns: (citation_count, influential_citations, paper_id) or (None, None, None)
    """
    if not doi:
        return None, None, None
    
    url = f"{SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}"
    params = {
        'fields': 'citationCount,influentialCitationCount,paperId,title,year'
    }
    headers = {'x-api-key': SEMANTIC_SCHOLAR_KEY}
    
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                return (
                    data.get('citationCount', 0),
                    data.get('influentialCitationCount', 0),
                    data.get('paperId', None)
                )
            elif response.status_code == 404:
                # Paper not found
                return None, None, None
            elif response.status_code == 429:
                # Rate limited - wait and retry
                if attempt < max_retries - 1:
                    print(f"  Rate limited, waiting {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"  Still rate limited after {max_retries} attempts, skipping...")
                    return None, None, None
            else:
                print(f"  Warning: Semantic Scholar returned {response.status_code}")
                return None, None, None
                
        except Exception as e:
            print(f"  Error querying Semantic Scholar: {e}")
            return None, None, None
    
    return None, None, None


def search_semantic_scholar_by_title(title, year=None):
    """
    Search Semantic Scholar by title
    Returns: (citation_count, influential_citations, paper_id) or (None, None, None)
    """
    if not title:
        return None, None, None
    
    url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
    params = {
        'query': title,
        'limit': 1,
        'fields': 'citationCount,influentialCitationCount,paperId,title,year'
    }
    headers = {'x-api-key': SEMANTIC_SCHOLAR_KEY}
    
    if year:
        params['year'] = str(year)
    
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                papers = data.get('data', [])
                
                if papers:
                    paper = papers[0]
                    # Verify title similarity (basic check)
                    found_title = paper.get('title', '').lower()
                    query_title = title.lower()
                    
                    # Simple similarity check
                    if query_title[:30] in found_title or found_title[:30] in query_title:
                        return (
                            paper.get('citationCount', 0),
                            paper.get('influentialCitationCount', 0),
                            paper.get('paperId', None)
                        )
                
                return None, None, None
            elif response.status_code == 429:
                # Rate limited - wait and retry
                if attempt < max_retries - 1:
                    print(f"  Rate limited, waiting {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"  Still rate limited after {max_retries} attempts, skipping...")
                    return None, None, None
            else:
                return None, None, None
                
        except Exception as e:
            print(f"  Error querying Semantic Scholar: {e}")
            return None, None, None
    
    return None, None, None


def add_citation_counts_to_csv(csv_path=None, output_path=None):
    """
    Add citation counts to existing library CSV
    """
    
    if csv_path is None:
        csv_path = f"{OUTPUT_DIR}/{DEFAULT_CSV}"
    
    if output_path is None:
        output_path = f"{OUTPUT_DIR}/library_with_citations.csv"
    
    # Load existing CSV
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"ERROR: {csv_path} not found!")
        print("Run fetch_library.py first")
        return
    
    print(f"Loaded {len(df)} papers from {csv_path}")
    print("\nFetching citation counts from Semantic Scholar...")
    print("(This may take a few minutes...)\n")
    
    # Add new columns
    df['citations'] = None
    df['influential_citations'] = None
    df['semantic_scholar_id'] = None
    
    found_count = 0
    not_found_count = 0
    
    for idx, row in df.iterrows():
        if (idx + 1) % 10 == 0:
            print(f"  Processed {idx + 1}/{len(df)} papers... (Found: {found_count}, Not found: {not_found_count})")
        
        title = row['title']
        doi = row.get('doi', '')
        year = row.get('year', '')
        
        # Try DOI first (most reliable)
        if doi:
            citations, influential, paper_id = search_semantic_scholar_by_doi(doi)
            
            if citations is not None:
                df.at[idx, 'citations'] = citations
                df.at[idx, 'influential_citations'] = influential
                df.at[idx, 'semantic_scholar_id'] = paper_id
                found_count += 1
                continue
        
        # Fallback to title search
        if title:
            citations, influential, paper_id = search_semantic_scholar_by_title(title, year)
            
            if citations is not None:
                df.at[idx, 'citations'] = citations
                df.at[idx, 'influential_citations'] = influential
                df.at[idx, 'semantic_scholar_id'] = paper_id
                found_count += 1
            else:
                not_found_count += 1
        
        # Rate limiting - be nice to Semantic Scholar
        time.sleep(5)  # 5 seconds between requests
    
    print(f"\n  Processed {len(df)} papers total")
    print(f"  Found citations: {found_count}")
    print(f"  Not found: {not_found_count}")
    
    # Convert citation columns to numeric
    df['citations'] = pd.to_numeric(df['citations'], errors='coerce')
    df['influential_citations'] = pd.to_numeric(df['influential_citations'], errors='coerce')
    
    # Reorder columns - put citations near the front
    cols = df.columns.tolist()
    
    # Move citation columns after score/quality
    citation_cols = ['citations', 'influential_citations', 'semantic_scholar_id']
    
    # Remove them from current position
    for col in citation_cols:
        if col in cols:
            cols.remove(col)
    
    # Insert after 'priority' if it exists
    if 'priority' in cols:
        insert_pos = cols.index('priority') + 1
    elif 'quality' in cols:
        insert_pos = cols.index('quality') + 1
    else:
        insert_pos = 5
    
    for col in reversed(citation_cols):
        cols.insert(insert_pos, col)
    
    df = df[cols]
    
    # Save
    df.to_csv(output_path, index=False)
    print(f"\n✓ Saved to {output_path}")
    
    # Print summary statistics
    print("\n" + "="*60)
    print("CITATION STATISTICS")
    print("="*60)
    
    papers_with_citations = df[df['citations'].notna()]
    
    if len(papers_with_citations) > 0:
        print(f"\nPapers with citation data: {len(papers_with_citations)}")
        print(f"Total citations: {int(papers_with_citations['citations'].sum())}")
        print(f"Average citations: {papers_with_citations['citations'].mean():.1f}")
        print(f"Median citations: {papers_with_citations['citations'].median():.1f}")
        print(f"Max citations: {int(papers_with_citations['citations'].max())}")
        
        # Top cited papers
        print("\nTop 10 most cited papers in your library:")
        top_cited = papers_with_citations.nlargest(10, 'citations')[['title', 'year', 'citations', 'influential_citations']]
        print(top_cited.to_string(index=False))
        
        # Highly cited but unread
        if 'status' in df.columns:
            unread_cited = papers_with_citations[
                (papers_with_citations['status'] == 'unread') & 
                (papers_with_citations['citations'] >= papers_with_citations['citations'].quantile(0.75))
            ]
            
            if len(unread_cited) > 0:
                print(f"\nHighly cited papers you haven't read yet: {len(unread_cited)}")
                print(unread_cited[['title', 'year', 'citations']].head(10).to_string(index=False))
    
    print("\n" + "="*60)
    
    return df


def update_zotero_with_citation_tags(zot, df):
    """
    Optional: Add citation count as tags in Zotero
    Tags like 'citations:100', 'highly-cited'
    """
    
    print("\nUpdating Zotero with citation tags...")
    
    papers_with_citations = df[df['citations'].notna()]
    
    if len(papers_with_citations) == 0:
        print("No citation data to add to Zotero")
        return
    
    # Define thresholds
    high_citation_threshold = papers_with_citations['citations'].quantile(0.9)  # Top 10%
    
    for idx, row in papers_with_citations.iterrows():
        item_key = row['key']
        citations = int(row['citations'])
        
        try:
            # Fetch item
            item = zot.item(item_key)
            tags = item['data'].get('tags', [])
            
            # Remove old citation tags
            tags = [t for t in tags if not t.get('tag', '').startswith('citations:')]
            tags = [t for t in tags if t.get('tag', '') != 'highly-cited']
            
            # Add new citation tag
            tags.append({'tag': f'citations:{citations}'})
            
            # Add highly-cited tag if applicable
            if citations >= high_citation_threshold:
                tags.append({'tag': 'highly-cited'})
            
            # Update item
            item['data']['tags'] = tags
            zot.update_item(item)
            
            if (idx + 1) % 10 == 0:
                print(f"  Updated {idx + 1}/{len(papers_with_citations)} items...")
            
            time.sleep(1.0)  # Rate limit
            
        except Exception as e:
            print(f"  Error updating {row['title'][:50]}: {e}")
    
    print(f"\n✓ Updated {len(papers_with_citations)} items in Zotero")

def update_zotero_with_extra_field(zot, df):
    """
    Store Semantic Scholar IDs in Zotero's Extra field
    Format: "Semantic Scholar ID: abc123xyz"
    """
    
    print("\nUpdating Zotero Extra fields with Semantic Scholar IDs...")
    
    papers_with_ids = df[df['semantic_scholar_id'].notna()]
    
    if len(papers_with_ids) == 0:
        print("No Semantic Scholar IDs to add to Zotero")
        return
    
    success_count = 0
    error_count = 0
    
    for idx, row in papers_with_ids.iterrows():
        item_key = row['key']
        ss_id = row['semantic_scholar_id']
        
        try:
            # Fetch item
            item = zot.item(item_key)
            
            # Get existing Extra field content
            existing_extra = item['data'].get('extra', '').strip()
            
            # Check if SS ID already exists
            lines = existing_extra.split('\n') if existing_extra else []
            
            # Remove any old SS ID lines
            lines = [line for line in lines if not line.startswith('Semantic Scholar ID:')]
            
            # Add new SS ID line
            lines.append(f'Semantic Scholar ID: {ss_id}')
            
            # Rejoin with newlines
            new_extra = '\n'.join(lines)
            
            # Update item
            item['data']['extra'] = new_extra
            zot.update_item(item)
            
            success_count += 1
            
            if (success_count + error_count) % 10 == 0:
                print(f"  Processed {success_count + error_count}/{len(papers_with_ids)} items...")
            
            time.sleep(1)  # Rate limit for Zotero API
            
        except Exception as e:
            error_count += 1
            print(f"  Error updating {row['title'][:50]}: {e}")
    
    print(f"\n✓ Updated {success_count} items in Zotero")
    if error_count > 0:
        print(f"⚠️  {error_count} items failed to update")


def main():
    """Main function"""
    
    import sys
    
    # Add citation counts to CSV
    df = add_citation_counts_to_csv()
    
    if df is None:
        return
    
    zot = None
    
    # Optionally store SS IDs in Zotero Extra field
    response = input("\nStore Semantic Scholar IDs in Zotero Extra field? (y/n): ")
    
    if response.lower() == 'y':
        if zot is None:
            zot = zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)
        update_zotero_with_extra_field(zot, df)
        print("\n✓ Semantic Scholar IDs stored in Zotero Extra field!")
        
    # Optionally update Zotero with tags
    response = input("\nAdd citation counts as tags in Zotero? (y/n): ")
    
    if response.lower() == 'y':
        if zot is None:
            zot = zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)
        update_zotero_with_citation_tags(zot, df)
        print("\n✓ Citation tags added to Zotero!")
        print("  - Tags like 'citations:50' added")
        print("  - 'highly-cited' tag added to top 10%")


if __name__ == '__main__':
    main()
