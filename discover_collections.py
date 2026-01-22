#!/usr/bin/env python3
"""
Collection-aware paper discovery
Discover papers relevant to specific collections/projects
"""

import time
import os
import requests
import pandas as pd
from collections import Counter
from config import OUTPUT_DIR, DEFAULT_CSV


SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"


def get_paper_references(paper_id, limit=100):
    """Get papers that this paper cites"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/references"
    params = {
        'fields': 'title,year,citationCount,authors,paperId,influentialCitationCount',
        'limit': limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        elif response.status_code == 429:
            print("  Rate limited, waiting...")
            time.sleep(30)
            return []
        else:
            return []
    except Exception as e:
        return []


def get_paper_citations(paper_id, limit=100):
    """Get papers that cite this paper"""
    url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/citations"
    params = {
        'fields': 'title,year,citationCount,authors,paperId,influentialCitationCount',
        'limit': limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        elif response.status_code == 429:
            print("  Rate limited, waiting...")
            time.sleep(30)
            return []
        else:
            return []
    except Exception as e:
        return []


def get_recommended_papers(paper_id, limit=10):
    """Get Semantic Scholar's ML recommendations"""
    url = f"{SEMANTIC_SCHOLAR_API}/recommendations/v1/papers/forpaper/{paper_id}"
    params = {
        'fields': 'title,year,citationCount,authors,paperId,influentialCitationCount',
        'limit': limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('recommendedPapers', [])
        elif response.status_code == 429:
            print("  Rate limited, waiting...")
            time.sleep(30)
            return []
        else:
            return []
    except Exception as e:
        return []


def get_available_collections(df):
    """Get list of collections"""
    collection_cols = [col for col in df.columns if col.startswith('in_')]
    
    if len(collection_cols) == 0:
        return []
    
    collections = []
    for col in collection_cols:
        name = col[3:]
        count = df[col].sum()
        collections.append({
            'name': name,
            'column': col,
            'count': int(count)
        })
    
    return sorted(collections, key=lambda x: x['count'], reverse=True)


def filter_by_collection(df, collection_column):
    """Filter to papers in specific collection"""
    if collection_column not in df.columns:
        return pd.DataFrame()
    
    return df[df[collection_column] == 1].copy()


def discover_for_collection(df, collection_name, collection_col, method='references', 
                            num_seeds=10, papers_per_seed=20):
    """
    Discover papers for a specific collection
    Uses papers IN that collection as seeds
    """
    
    print(f"\n{'='*70}")
    print(f"🔍 DISCOVERING FOR COLLECTION: {collection_name}")
    print(f"   Method: {method.upper()}")
    print(f"{'='*70}\n")
    
    # Get papers in this collection
    coll_df = filter_by_collection(df, collection_col)
    
    if len(coll_df) == 0:
        print("No papers in this collection!")
        return pd.DataFrame()
    
    # Get seed papers (highest scored papers in this collection with SS IDs)
    seeds = coll_df[
        (coll_df['score'].notna()) & 
        (coll_df['semantic_scholar_id'].notna())
    ].copy()
    
    if len(seeds) == 0:
        # Fallback: use any papers with SS IDs
        seeds = coll_df[coll_df['semantic_scholar_id'].notna()].copy()
        
        if len(seeds) == 0:
            print("No papers with Semantic Scholar IDs in this collection!")
            print("Run add_citations.py first")
            return pd.DataFrame()
        
        print(f"⚠️  No scored papers in collection - using all {len(seeds)} papers as seeds")
    else:
        # Sort by score
        seeds = seeds.sort_values('score', ascending=False).head(num_seeds)
    
    print(f"Using {len(seeds)} seed papers from '{collection_name}':")
    for _, seed in seeds.iterrows():
        score = seed.get('score', 'N/A')
        print(f"  • {seed['title'][:55]}... (score: {score})")
    
    print(f"\nFetching {papers_per_seed} {method} per seed...\n")
    
    all_discovered = []
    
    for idx, seed in seeds.iterrows():
        paper_id = seed['semantic_scholar_id']
        print(f"[{idx+1}/{len(seeds)}] {seed['title'][:50]}...")
        
        if method == 'references':
            papers = get_paper_references(paper_id, limit=papers_per_seed)
            papers = [p['citedPaper'] for p in papers]
        elif method == 'citations':
            papers = get_paper_citations(paper_id, limit=papers_per_seed)
            papers = [p['citingPaper'] for p in papers]
        elif method == 'recommendations':
            papers = get_recommended_papers(paper_id, limit=papers_per_seed)
        else:
            return pd.DataFrame()
        
        print(f"  Found {len(papers)}")
        
        for paper in papers:
            all_discovered.append({
                'paperId': paper.get('paperId'),
                'title': paper.get('title'),
                'year': paper.get('year'),
                'citations': paper.get('citationCount', 0),
                'influential': paper.get('influentialCitationCount', 0),
                'authors': ', '.join([a.get('name', '') for a in paper.get('authors', [])[:3]]),
                'seed_paper': seed['title'][:40],
                'seed_collection': collection_name
            })
        
        time.sleep(3)  # Rate limiting
    
    if len(all_discovered) == 0:
        print("No papers discovered")
        return pd.DataFrame()
    
    discovered_df = pd.DataFrame(all_discovered)
    
    # Remove duplicates
    discovered_df = discovered_df.sort_values('citations', ascending=False)
    discovered_df = discovered_df.drop_duplicates(subset=['paperId'], keep='first')
    
    # Remove papers already in your library
    your_titles = set(df['title'].str.lower())
    discovered_df['title_lower'] = discovered_df['title'].str.lower()
    discovered_df = discovered_df[~discovered_df['title_lower'].isin(your_titles)]
    discovered_df = discovered_df.drop('title_lower', axis=1)
    
    print(f"\n✓ Discovered {len(discovered_df)} unique papers not in your library")
    
    return discovered_df


def discover_gaps_between_collections(df, coll1_col, coll2_col, coll1_name, coll2_name):
    """
    Find papers in Collection 1 that might be relevant to Collection 2
    (and vice versa) based on citation overlap
    
    Example: Papers in "Market Microstructure" that cite papers in "Systemic Risk"
    """
    
    print(f"\n{'='*70}")
    print(f"🔗 FINDING CONNECTIONS BETWEEN COLLECTIONS")
    print(f"   {coll1_name} ⟷ {coll2_name}")
    print(f"{'='*70}\n")
    
    coll1_df = filter_by_collection(df, coll1_col)
    coll2_df = filter_by_collection(df, coll2_col)
    
    if len(coll1_df) == 0 or len(coll2_df) == 0:
        print("One or both collections are empty")
        return pd.DataFrame()
    
    # Get papers with SS IDs in each collection
    coll1_ids = set(coll1_df[coll1_df['semantic_scholar_id'].notna()]['semantic_scholar_id'])
    coll2_ids = set(coll2_df[coll2_df['semantic_scholar_id'].notna()]['semantic_scholar_id'])
    
    if len(coll1_ids) == 0 or len(coll2_ids) == 0:
        print("Need Semantic Scholar IDs - run add_citations.py first")
        return pd.DataFrame()
    
    print(f"Analyzing citation patterns...")
    print(f"  {coll1_name}: {len(coll1_ids)} papers")
    print(f"  {coll2_name}: {len(coll2_ids)} papers")
    
    # Sample to avoid too many API calls
    sample1 = list(coll1_ids)[:10]
    sample2 = list(coll2_ids)[:10]
    
    bridge_papers = []
    
    # Find papers that cite both collections
    print(f"\nSearching for papers citing both collections...")
    
    for i, paper_id in enumerate(sample1[:5], 1):
        print(f"[{i}/5] Checking citations to collection 1...")
        
        citing = get_paper_citations(paper_id, limit=50)
        
        for cite in citing:
            citing_paper = cite['citingPaper']
            citing_id = citing_paper.get('paperId')
            
            if not citing_id:
                continue
            
            # Check if this paper also cites collection 2
            refs = get_paper_references(citing_id, limit=50)
            ref_ids = {r['citedPaper'].get('paperId') for r in refs}
            
            if ref_ids & coll2_ids:  # Intersection
                bridge_papers.append({
                    'paperId': citing_id,
                    'title': citing_paper.get('title'),
                    'year': citing_paper.get('year'),
                    'citations': citing_paper.get('citationCount', 0),
                    'bridge_type': f'Cites both {coll1_name} and {coll2_name}'
                })
            
            time.sleep(3)
    
    if len(bridge_papers) == 0:
        print("No bridge papers found (try running with more seeds)")
        return pd.DataFrame()
    
    bridge_df = pd.DataFrame(bridge_papers)
    bridge_df = bridge_df.drop_duplicates(subset=['paperId'])
    
    # Remove papers already in library
    your_titles = set(df['title'].str.lower())
    bridge_df['title_lower'] = bridge_df['title'].str.lower()
    bridge_df = bridge_df[~bridge_df['title_lower'].isin(your_titles)]
    bridge_df = bridge_df.drop('title_lower', axis=1)
    
    print(f"\n✓ Found {len(bridge_df)} bridge papers")
    
    return bridge_df


def main():
    """Main collection-aware discovery workflow"""
    
    # Use fresh export by default
    csv_path = f"{OUTPUT_DIR}/{DEFAULT_CSV}"
    
    # Check if citations file exists and is newer (discovery needs SS IDs)
    citations_path = f"{OUTPUT_DIR}/library_with_citations.csv"
    
    if os.path.exists(citations_path) and os.path.exists(csv_path):
        cite_time = os.path.getmtime(citations_path)
        export_time = os.path.getmtime(csv_path)
        
        if cite_time > export_time:
            csv_path = citations_path
    elif os.path.exists(citations_path):
        csv_path = citations_path
    
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"ERROR: {csv_path} not found!")
        print("Run fetch_library_with_collections.py first")
        return
    
    # Get collections
    collections = get_available_collections(df)
    
    if len(collections) == 0:
        print("No collections found!")
        print("Run fetch_library_with_collections.py to get collection data")
        return
    
    has_ss_ids = 'semantic_scholar_id' in df.columns and df['semantic_scholar_id'].notna().any()
    
    if not has_ss_ids:
        print("\n⚠️  No Semantic Scholar IDs found!")
        print("Run add_citations.py first")
        return
    
    print("\n" + "="*70)
    print("🔍 COLLECTION-AWARE PAPER DISCOVERY")
    print("="*70)
    print(f"Total papers: {len(df)}")
    print(f"Collections: {len(collections)}")
    
    # Show collections
    print("\n" + "="*70)
    print("AVAILABLE COLLECTIONS")
    print("="*70)
    
    for idx, coll in enumerate(collections[:20], 1):
        print(f"{idx:2d}. {coll['name']:50s} ({coll['count']:3d} papers)")
    
    if len(collections) > 20:
        print(f"... and {len(collections) - 20} more")
    
    print("\n" + "="*70)
    print("DISCOVERY OPTIONS")
    print("="*70)
    print("1. Discover for single collection")
    print("2. Discover for multiple collections")
    print("3. Find bridge papers between collections")
    print("4. Exit")
    
    choice = input("\nChoose option (1-4): ").strip()
    
    if choice == '1':
        # Single collection
        coll_num = input(f"\nEnter collection number (1-{len(collections)}): ").strip()
        
        try:
            idx = int(coll_num) - 1
            if 0 <= idx < len(collections):
                coll = collections[idx]
                
                print("\nDiscovery method:")
                print("1. Backward (foundational papers)")
                print("2. Forward (recent papers)")
                print("3. ML recommendations")
                
                method_choice = input("Choose method (1-3): ").strip()
                
                method_map = {'1': 'references', '2': 'citations', '3': 'recommendations'}
                method = method_map.get(method_choice, 'references')
                
                discovered = discover_for_collection(
                    df, 
                    coll['name'], 
                    coll['column'],
                    method=method,
                    num_seeds=10,
                    papers_per_seed=30
                )
                
                if len(discovered) > 0:
                    discovered = discovered.sort_values('citations', ascending=False)
                    
                    print("\n" + "="*70)
                    print(f"📚 DISCOVERED PAPERS FOR: {coll['name']}")
                    print("="*70)
                    print(discovered[['title', 'year', 'citations', 'authors']].head(20).to_string(index=False))
                    
                    output_path = f"{OUTPUT_DIR}/discovered_{coll['name'].replace('/', '_')}_{method}.csv"
                    discovered.to_csv(output_path, index=False)
                    print(f"\n✓ Saved {len(discovered)} papers to {output_path}")
            else:
                print("Invalid number")
        except ValueError:
            print("Invalid input")
    
    elif choice == '2':
        # Multiple collections
        print("\nEnter collection numbers separated by commas (e.g., 1,3,5):")
        nums = input("> ").strip()
        
        print("\nDiscovery method:")
        print("1. Backward (foundational)")
        print("2. Forward (recent)")
        print("3. ML recommendations")
        
        method_choice = input("Choose method (1-3): ").strip()
        method_map = {'1': 'references', '2': 'citations', '3': 'recommendations'}
        method = method_map.get(method_choice, 'references')
        
        try:
            indices = [int(n.strip()) - 1 for n in nums.split(',')]
            selected = [collections[i] for i in indices if 0 <= i < len(collections)]
            
            all_discovered = []
            
            for coll in selected:
                discovered = discover_for_collection(
                    df,
                    coll['name'],
                    coll['column'],
                    method=method,
                    num_seeds=5,  # Fewer seeds when doing multiple
                    papers_per_seed=20
                )
                
                if len(discovered) > 0:
                    all_discovered.append(discovered)
            
            if all_discovered:
                # Combine and deduplicate
                combined = pd.concat(all_discovered, ignore_index=True)
                combined = combined.sort_values('citations', ascending=False)
                combined = combined.drop_duplicates(subset=['paperId'], keep='first')
                
                print("\n" + "="*70)
                print(f"📚 COMBINED DISCOVERIES ({len(selected)} collections)")
                print("="*70)
                print(combined[['title', 'year', 'citations', 'seed_collection']].head(30).to_string(index=False))
                
                output_path = f"{OUTPUT_DIR}/discovered_multiple_collections_{method}.csv"
                combined.to_csv(output_path, index=False)
                print(f"\n✓ Saved {len(combined)} papers to {output_path}")
        
        except (ValueError, IndexError):
            print("Invalid input")
    
    elif choice == '3':
        # Bridge papers
        print("\nFind papers connecting two collections")
        coll1_num = input(f"First collection (1-{len(collections)}): ").strip()
        coll2_num = input(f"Second collection (1-{len(collections)}): ").strip()
        
        try:
            idx1 = int(coll1_num) - 1
            idx2 = int(coll2_num) - 1
            
            if 0 <= idx1 < len(collections) and 0 <= idx2 < len(collections):
                coll1 = collections[idx1]
                coll2 = collections[idx2]
                
                bridge = discover_gaps_between_collections(
                    df,
                    coll1['column'],
                    coll2['column'],
                    coll1['name'],
                    coll2['name']
                )
                
                if len(bridge) > 0:
                    bridge = bridge.sort_values('citations', ascending=False)
                    
                    print("\n" + "="*70)
                    print(f"🔗 BRIDGE PAPERS")
                    print("="*70)
                    print(bridge[['title', 'year', 'citations', 'bridge_type']].head(20).to_string(index=False))
                    
                    output_path = f"{OUTPUT_DIR}/bridge_{coll1['name']}_to_{coll2['name']}.csv"
                    output_path = output_path.replace('/', '_')
                    bridge.to_csv(output_path, index=False)
                    print(f"\n✓ Saved {len(bridge)} papers to {output_path}")
            else:
                print("Invalid numbers")
        except ValueError:
            print("Invalid input")
    
    elif choice == '4':
        print("Exiting")
        return
    
    else:
        print("Invalid choice")


if __name__ == '__main__':
    main()
