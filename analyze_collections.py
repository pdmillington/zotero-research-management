#!/usr/bin/env python3
"""
Collection-aware library analysis with citation scoring
Analyze specific collections (projects, topics, etc.)
"""

import pandas as pd
import numpy as np
import os
import sys
from config import OUTPUT_DIR, DEFAULT_CSV


def calculate_citation_percentile(df):
    """Calculate citation percentile for each paper"""
    
    if 'citations' not in df.columns:
        print("Warning: No citation data found. Run add_citations.py first.")
        df['citation_percentile'] = 50
        return df
    
    papers_with_citations = df[df['citations'].notna()].copy()
    
    if len(papers_with_citations) == 0:
        df['citation_percentile'] = 50
        return df
    
    df['citation_percentile'] = df['citations'].rank(pct=True) * 100
    df['citation_percentile'] = df['citation_percentile'].fillna(50)
    
    return df


def calculate_composite_score(df, use_citations=True):
    """Calculate composite score from individual ratings"""
    
    scored = df[df['score'].notna() | df['quality'].notna()].copy()
    
    if len(scored) == 0:
        return pd.DataFrame()
    
    scored['score'] = scored['score'].fillna(scored['score'].median())
    scored['quality'] = scored['quality'].fillna(scored['quality'].median()) if 'quality' in scored.columns else 3
    
    priority_map = {'high': 3, 'medium': 2, 'low': 1}
    scored['priority_num'] = scored['priority'].map(priority_map).fillna(2)
    
    scored = calculate_citation_percentile(scored)
    scored['citation_score'] = (scored['citation_percentile'] / 100) * 4 + 1
    
    if use_citations and 'citations' in scored.columns and scored['citations'].notna().any():
        scored['composite'] = (
            scored['score'] * 0.35 +
            scored['quality'] * 0.25 +
            scored['priority_num'] * 0.15 +
            scored['citation_score'] * 0.25
        )
    else:
        scored['composite'] = (
            scored['score'] * 0.5 +
            scored['quality'] * 0.3 +
            scored['priority_num'] * 0.2
        )
    
    return scored


def get_available_collections(df):
    """Get list of collections with paper counts"""
    
    # Find all collection columns (start with 'in_')
    collection_cols = [col for col in df.columns if col.startswith('in_')]
    
    if len(collection_cols) == 0:
        print("No collection columns found!")
        print("Use fetch_library_with_collections.py to get collection data")
        return []
    
    collections = []
    for col in collection_cols:
        name = col[3:]  # Remove 'in_' prefix
        count = df[col].sum()
        collections.append({
            'name': name,
            'column': col,
            'count': int(count)
        })
    
    return sorted(collections, key=lambda x: x['count'], reverse=True)


def filter_by_collection(df, collection_column):
    """Filter dataframe to only papers in specified collection"""
    
    if collection_column not in df.columns:
        print(f"Collection column '{collection_column}' not found!")
        return pd.DataFrame()
    
    filtered = df[df[collection_column] == 1].copy()
    return filtered


def analyze_collection(df, collection_name, collection_col, use_citations=True):
    """Analyze a specific collection"""
    
    coll_df = filter_by_collection(df, collection_col)
    
    if len(coll_df) == 0:
        print(f"No papers in collection: {collection_name}")
        return
    
    has_citations = 'citations' in coll_df.columns and coll_df['citations'].notna().any()
    
    print("\n" + "="*70)
    print(f"📁 COLLECTION: {collection_name}")
    print("="*70)
    print(f"Total papers: {len(coll_df)}")
    print(f"Scored papers: {coll_df['score'].notna().sum()}")
    print(f"With citations: {coll_df['citations'].notna().sum() if has_citations else 0}")
    print(f"Unread papers: {(coll_df['status'] == 'unread').sum() if 'status' in coll_df.columns else 'unknown'}")
    
    # Reading list for this collection
    print("\n" + "="*70)
    print(f"📚 TOP PAPERS IN: {collection_name}")
    print("="*70)
    
    scored = calculate_composite_score(coll_df, use_citations=use_citations and has_citations)
    
    if len(scored) > 0:
        reading_list = scored.sort_values('composite', ascending=False)
        
        display_cols = ['title', 'year', 'score', 'composite']
        if 'citations' in reading_list.columns:
            display_cols.insert(3, 'citations')
        if 'topics' in reading_list.columns:
            display_cols.append('topics')
        
        available_cols = [c for c in display_cols if c in reading_list.columns]
        print(reading_list[available_cols].head(15).to_string(index=False))
    
    # Unread papers in this collection
    if 'status' in coll_df.columns:
        unread = coll_df[coll_df['status'] == 'unread']
        if len(unread) > 0:
            print("\n" + "="*70)
            print(f"📖 UNREAD IN: {collection_name}")
            print("="*70)
            
            unread_scored = calculate_composite_score(unread, use_citations=use_citations and has_citations)
            if len(unread_scored) > 0:
                unread_list = unread_scored.sort_values('composite', ascending=False)
                display_cols = ['title', 'year', 'score']
                if 'citations' in unread_list.columns:
                    display_cols.append('citations')
                available_cols = [c for c in display_cols if c in unread_list.columns]
                print(unread_list[available_cols].head(10).to_string(index=False))
    
    # Hidden gems in this collection
    if has_citations:
        unscored = coll_df[coll_df['score'].isna() & coll_df['citations'].notna()].copy()
        
        if len(unscored) > 0:
            coll_df = calculate_citation_percentile(coll_df)
            unscored = coll_df[coll_df['score'].isna() & coll_df['citations'].notna()].copy()
            high_impact = unscored[unscored['citation_percentile'] >= 75].sort_values('citations', ascending=False)
            
            if len(high_impact) > 0:
                print("\n" + "="*70)
                print(f"💎 HIDDEN GEMS IN: {collection_name}")
                print("="*70)
                print(high_impact[['title', 'year', 'citations']].head(10).to_string(index=False))
    
    # Citation stats for this collection
    if has_citations:
        papers_with_cites = coll_df[coll_df['citations'].notna()]
        
        if len(papers_with_cites) > 0:
            print("\n" + "="*70)
            print(f"📊 CITATION STATS: {collection_name}")
            print("="*70)
            print(f"Total citations: {papers_with_cites['citations'].sum():.0f}")
            print(f"Average citations: {papers_with_cites['citations'].mean():.1f}")
            print(f"Median citations: {papers_with_cites['citations'].median():.0f}")
            print(f"Most cited: {papers_with_cites['citations'].max():.0f}")
            
            print("\nTop 5 most cited in this collection:")
            top_cited = papers_with_cites.nlargest(5, 'citations')
            print(top_cited[['title', 'year', 'citations']].to_string(index=False))


def compare_collections(df, collection_cols, use_citations=True):
    """Compare metrics across multiple collections"""
    
    print("\n" + "="*70)
    print("📊 COLLECTION COMPARISON")
    print("="*70)
    
    has_citations = 'citations' in df.columns and df['citations'].notna().any()
    
    comparison = []
    
    for col_info in collection_cols:
        col = col_info['column']
        name = col_info['name']
        
        coll_df = filter_by_collection(df, col)
        
        if len(coll_df) == 0:
            continue
        
        stats = {
            'Collection': name,
            'Papers': len(coll_df),
            'Scored': coll_df['score'].notna().sum(),
        }
        
        if 'score' in coll_df.columns and coll_df['score'].notna().any():
            stats['Avg Score'] = coll_df['score'].mean()
        
        if has_citations:
            papers_with_cites = coll_df[coll_df['citations'].notna()]
            if len(papers_with_cites) > 0:
                stats['With Cites'] = len(papers_with_cites)
                stats['Total Cites'] = papers_with_cites['citations'].sum()
                stats['Avg Cites'] = papers_with_cites['citations'].mean()
                stats['Max Cites'] = papers_with_cites['citations'].max()
        
        if 'status' in coll_df.columns:
            stats['Unread'] = (coll_df['status'] == 'unread').sum()
        
        comparison.append(stats)
    
    if len(comparison) > 0:
        comp_df = pd.DataFrame(comparison)
        
        # Sort by total citations if available, else by paper count
        if 'Total Cites' in comp_df.columns:
            comp_df = comp_df.sort_values('Total Cites', ascending=False)
        else:
            comp_df = comp_df.sort_values('Papers', ascending=False)
        
        print(comp_df.to_string(index=False))


def main():
    """Main workflow with collection selection"""
    
    # Use fresh export by default (has current scores from Zotero)
    csv_path = f"{OUTPUT_DIR}/{DEFAULT_CSV}"
    
    # Check if citations file exists and is newer (optional enhancement)
    citations_path = f"{OUTPUT_DIR}/library_with_citations.csv"
    
    if os.path.exists(citations_path) and os.path.exists(csv_path):
        cite_time = os.path.getmtime(citations_path)
        export_time = os.path.getmtime(csv_path)
        
        if cite_time > export_time:
            print(f"ℹ️  Using citation-enhanced file (newer)")
            csv_path = citations_path
        else:
            print(f"ℹ️  Using fresh export (citations file is older)")
    elif os.path.exists(citations_path):
        print(f"ℹ️  Fresh export not found, using citation file")
        csv_path = citations_path
    
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"ERROR: {csv_path} not found!")
        print("Run fetch_library_with_collections.py first")
        return
    
    # Get available collections
    collections = get_available_collections(df)
    
    if len(collections) == 0:
        print("No collections found!")
        print("Run fetch_library_with_collections.py to get collection data")
        return
    
    has_citations = 'citations' in df.columns and df['citations'].notna().any()
    
    print("\n" + "="*70)
    print("🗂️  COLLECTION-AWARE ANALYSIS")
    print("="*70)
    print(f"Total papers: {len(df)}")
    print(f"Collections found: {len(collections)}")
    print(f"Citation data: {'Yes' if has_citations else 'No'}")
    
    # Show available collections
    print("\n" + "="*70)
    print("AVAILABLE COLLECTIONS")
    print("="*70)
    
    for idx, coll in enumerate(collections[:20], 1):  # Show top 20
        print(f"{idx:2d}. {coll['name']:50s} ({coll['count']:3d} papers)")
    
    if len(collections) > 20:
        print(f"... and {len(collections) - 20} more")
    
    print("\n" + "="*70)
    print("OPTIONS")
    print("="*70)
    print("1. Analyze specific collection")
    print("2. Compare all collections")
    print("3. Analyze multiple collections")
    print("4. Exit")
    
    choice = input("\nChoose option (1-4): ").strip()
    
    if choice == '1':
        # Single collection analysis
        coll_num = input(f"\nEnter collection number (1-{len(collections)}): ").strip()
        
        try:
            idx = int(coll_num) - 1
            if 0 <= idx < len(collections):
                coll = collections[idx]
                analyze_collection(df, coll['name'], coll['column'], use_citations=has_citations)
            else:
                print("Invalid collection number")
        except ValueError:
            print("Invalid input")
    
    elif choice == '2':
        # Compare all collections
        compare_collections(df, collections, use_citations=has_citations)
    
    elif choice == '3':
        # Multiple collection analysis
        print("\nEnter collection numbers separated by commas (e.g., 1,3,5):")
        nums = input("> ").strip()
        
        try:
            indices = [int(n.strip()) - 1 for n in nums.split(',')]
            selected = [collections[i] for i in indices if 0 <= i < len(collections)]
            
            # First compare them
            compare_collections(df, selected, use_citations=has_citations)
            
            # Then analyze each
            for coll in selected:
                analyze_collection(df, coll['name'], coll['column'], use_citations=has_citations)
        except (ValueError, IndexError):
            print("Invalid input")
    
    elif choice == '4':
        print("Exiting")
        return
    
    else:
        print("Invalid choice")


if __name__ == '__main__':
    main()
