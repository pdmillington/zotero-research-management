#!/usr/bin/env python3
"""
Discover influential papers you should add to your library
Uses Semantic Scholar's recommendations and reference mining
"""

import time
import os
import requests
import pandas as pd
from collections import Counter
from config import OUTPUT_DIR, DEFAULT_CSV


SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"


def get_paper_references(paper_id, limit=100):
    """Get papers that this paper cites (backward citations)"""
    
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
        print(f"  Error: {e}")
        return []


def get_paper_citations(paper_id, limit=100):
    """Get papers that cite this paper (forward citations)"""
    
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
        print(f"  Error: {e}")
        return []


def get_recommended_papers(paper_id, limit=10):
    """Get Semantic Scholar's ML-based recommendations"""
    
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
        print(f"  Error: {e}")
        return []


def discover_from_seed_papers(df, method='references', num_seeds=10, papers_per_seed=20):
    """
    Discover papers based on your highest-rated papers
    
    Methods:
    - 'references': Papers cited by your top papers (foundational work)
    - 'citations': Papers citing your top papers (recent work)
    - 'recommendations': ML-based recommendations from Semantic Scholar
    """
    
    print(f"\n{'='*60}")
    print(f"DISCOVERING PAPERS VIA {method.upper()}")
    print(f"{'='*60}\n")
    
    # Get seed papers (your highest-rated papers with Semantic Scholar IDs)
    seeds = df[
        (df['score'].notna()) & 
        (df['semantic_scholar_id'].notna())
    ].copy()
    
    if len(seeds) == 0:
        print("No papers with Semantic Scholar IDs found!")
        print("Run add_citations.py first")
        return pd.DataFrame()
    
    # Sort by score and take top N
    seeds = seeds.sort_values('score', ascending=False).head(num_seeds)
    
    print(f"Using {len(seeds)} seed papers:")
    for _, seed in seeds.iterrows():
        print(f"  • {seed['title'][:60]}... (score: {seed['score']})")
    
    print(f"\nFetching {papers_per_seed} {method} per seed paper...\n")
    
    all_discovered = []
    
    for idx, seed in seeds.iterrows():
        paper_id = seed['semantic_scholar_id']
        print(f"[{idx+1}/{len(seeds)}] Processing: {seed['title'][:50]}...")
        
        if method == 'references':
            papers = get_paper_references(paper_id, limit=papers_per_seed)
            papers = [p['citedPaper'] for p in papers]
        elif method == 'citations':
            papers = get_paper_citations(paper_id, limit=papers_per_seed)
            papers = [p['citingPaper'] for p in papers]
        elif method == 'recommendations':
            papers = get_recommended_papers(paper_id, limit=papers_per_seed)
        else:
            print(f"Unknown method: {method}")
            return pd.DataFrame()
        
        print(f"  Found {len(papers)} papers")
        
        for paper in papers:
            all_discovered.append({
                'paperId': paper.get('paperId'),
                'title': paper.get('title'),
                'year': paper.get('year'),
                'citations': paper.get('citationCount', 0),
                'influential': paper.get('influentialCitationCount', 0),
                'authors': ', '.join([a.get('name', '') for a in paper.get('authors', [])[:3]]),
                'seed_paper': seed['title'][:40]
            })
        
        time.sleep(3)  # Rate limiting
    
    if len(all_discovered) == 0:
        print("No papers discovered")
        return pd.DataFrame()
    
    discovered_df = pd.DataFrame(all_discovered)
    
    # Remove duplicates (keep highest cited version)
    discovered_df = discovered_df.sort_values('citations', ascending=False)
    discovered_df = discovered_df.drop_duplicates(subset=['paperId'], keep='first')
    
    # Remove papers already in your library (by title matching)
    your_titles = set(df['title'].str.lower())
    discovered_df['title_lower'] = discovered_df['title'].str.lower()
    discovered_df = discovered_df[~discovered_df['title_lower'].isin(your_titles)]
    discovered_df = discovered_df.drop('title_lower', axis=1)
    
    print(f"\n✓ Discovered {len(discovered_df)} unique papers not in your library")
    
    return discovered_df


def find_most_cited_in_field(topic_query, year_min=2015, limit=50):
    """
    Find most cited papers in a field using keyword search
    Useful for discovering seminal papers you might have missed
    """
    
    print(f"\n{'='*60}")
    print(f"SEARCHING FOR: '{topic_query}'")
    print(f"{'='*60}\n")
    
    url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
    params = {
        'query': topic_query,
        'year': f'{year_min}-',
        'limit': limit,
        'fields': 'title,year,citationCount,authors,paperId,influentialCitationCount,abstract'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            papers = data.get('data', [])
            
            if len(papers) == 0:
                print("No papers found")
                return pd.DataFrame()
            
            results = []
            for paper in papers:
                results.append({
                    'paperId': paper.get('paperId'),
                    'title': paper.get('title'),
                    'year': paper.get('year'),
                    'citations': paper.get('citationCount', 0),
                    'influential': paper.get('influentialCitationCount', 0),
                    'authors': ', '.join([a.get('name', '') for a in paper.get('authors', [])[:3]]),
                    'abstract': paper.get('abstract', '')[:200] + '...' if paper.get('abstract') else ''
                })
            
            results_df = pd.DataFrame(results)
            results_df = results_df.sort_values('citations', ascending=False)
            
            print(f"✓ Found {len(results_df)} papers")
            
            return results_df
            
        elif response.status_code == 429:
            print("Rate limited")
            return pd.DataFrame()
        else:
            print(f"Error: {response.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()


def find_co_citation_network(df, min_connections=3):
    """
    Find papers frequently cited together with papers in your library
    (Co-citation analysis - papers cited by the same papers)
    
    This finds papers that are intellectually related to your collection
    """
    
    print(f"\n{'='*60}")
    print("CO-CITATION ANALYSIS")
    print("="*60)
    print("Finding papers frequently cited alongside papers in your library\n")
    
    # Get papers with Semantic Scholar IDs
    with_ids = df[df['semantic_scholar_id'].notna()].copy()
    
    if len(with_ids) < 5:
        print("Need at least 5 papers with Semantic Scholar IDs")
        return pd.DataFrame()
    
    # Sample 10-20 papers to avoid rate limits
    sample_papers = with_ids.sample(min(20, len(with_ids)))
    
    print(f"Analyzing {len(sample_papers)} papers from your library...\n")
    
    co_cited_counter = Counter()
    
    for idx, paper in sample_papers.iterrows():
        paper_id = paper['semantic_scholar_id']
        print(f"[{idx+1}/{len(sample_papers)}] Analyzing: {paper['title'][:50]}...")
        
        # Get papers that cite this paper
        citing_papers = get_paper_citations(paper_id, limit=50)
        
        if len(citing_papers) == 0:
            continue
        
        # For each citing paper, get what else it cites
        for citing in citing_papers[:5]:  # Limit to 5 to avoid too many API calls
            citing_id = citing['citingPaper'].get('paperId')
            if not citing_id:
                continue
            
            refs = get_paper_references(citing_id, limit=30)
            
            for ref in refs:
                ref_paper = ref['citedPaper']
                ref_id = ref_paper.get('paperId')
                
                # Count papers cited alongside your library papers
                if ref_id and ref_id != paper_id:
                    co_cited_counter[ref_id] += 1
            
            time.sleep(3)  # Rate limiting
    
    if len(co_cited_counter) == 0:
        print("No co-citations found")
        return pd.DataFrame()
    
    # Get papers cited at least min_connections times
    frequent = [(pid, count) for pid, count in co_cited_counter.items() if count >= min_connections]
    
    if len(frequent) == 0:
        print(f"No papers cited {min_connections}+ times alongside your library")
        return pd.DataFrame()
    
    print(f"\n✓ Found {len(frequent)} papers frequently co-cited with your library")
    
    # Fetch details for these papers
    # (Would need additional API calls - simplified here)
    
    return pd.DataFrame(frequent, columns=['paperId', 'co_citation_count'])


def main():
    """Main discovery workflow"""
    
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
        print("Run fetch_library.py first")
        return
    
    print("\n" + "="*60)
    print("🔍 PAPER DISCOVERY TOOL")
    print("="*60)
    print(f"Your library: {len(df)} papers")
    print(f"Scored: {df['score'].notna().sum()}")
    print(f"With Semantic Scholar IDs: {df['semantic_scholar_id'].notna().sum() if 'semantic_scholar_id' in df.columns else 0}")
    
    if 'semantic_scholar_id' not in df.columns or df['semantic_scholar_id'].notna().sum() == 0:
        print("\n⚠️  No Semantic Scholar IDs found!")
        print("Run add_citations.py first to enable discovery features")
        return
    
    print("\n" + "="*60)
    print("DISCOVERY METHODS")
    print("="*60)
    print("1. BACKWARD: Find foundational papers (what your top papers cite)")
    print("2. FORWARD: Find recent papers (what cites your top papers)")
    print("3. RECOMMENDATIONS: ML-based similar papers")
    print("4. TOPIC SEARCH: Most cited papers in a specific topic")
    print("="*60)
    
    choice = input("\nChoose method (1-4) or 'all': ")
    
    output_dir = f"{OUTPUT_DIR}"
    
    if choice in ['1', 'all']:
        # Backward discovery - foundational papers
        backward = discover_from_seed_papers(
            df, 
            method='references', 
            num_seeds=10, 
            papers_per_seed=30
        )
        
        if len(backward) > 0:
            backward = backward.sort_values('citations', ascending=False)
            
            print("\n" + "="*60)
            print("📚 TOP FOUNDATIONAL PAPERS TO ADD")
            print("="*60)
            print(backward[['title', 'year', 'citations', 'authors']].head(20).to_string(index=False))
            
            output_path = f"{output_dir}/discovered_foundational.csv"
            backward.to_csv(output_path, index=False)
            print(f"\n✓ Saved {len(backward)} papers to {output_path}")
    
    if choice in ['2', 'all']:
        # Forward discovery - recent papers
        forward = discover_from_seed_papers(
            df, 
            method='citations', 
            num_seeds=10, 
            papers_per_seed=30
        )
        
        if len(forward) > 0:
            forward = forward.sort_values('citations', ascending=False)
            
            print("\n" + "="*60)
            print("🆕 TOP RECENT PAPERS TO ADD")
            print("="*60)
            print(forward[['title', 'year', 'citations', 'authors']].head(20).to_string(index=False))
            
            output_path = f"{output_dir}/discovered_recent.csv"
            forward.to_csv(output_path, index=False)
            print(f"\n✓ Saved {len(forward)} papers to {output_path}")
    
    if choice in ['3', 'all']:
        # ML recommendations
        recommended = discover_from_seed_papers(
            df, 
            method='recommendations', 
            num_seeds=15, 
            papers_per_seed=10
        )
        
        if len(recommended) > 0:
            recommended = recommended.sort_values('citations', ascending=False)
            
            print("\n" + "="*60)
            print("🤖 ML-RECOMMENDED PAPERS TO ADD")
            print("="*60)
            print(recommended[['title', 'year', 'citations', 'authors']].head(20).to_string(index=False))
            
            output_path = f"{output_dir}/discovered_recommended.csv"
            recommended.to_csv(output_path, index=False)
            print(f"\n✓ Saved {len(recommended)} papers to {output_path}")
    
    if choice == '4':
        # Topic search
        print("\nEnter topic/keywords (e.g., 'minority game agent-based model'):")
        query = input("> ")
        
        if query.strip():
            topic_papers = find_most_cited_in_field(query, year_min=2015, limit=50)
            
            if len(topic_papers) > 0:
                # Remove papers already in library
                your_titles = set(df['title'].str.lower())
                topic_papers['title_lower'] = topic_papers['title'].str.lower()
                topic_papers = topic_papers[~topic_papers['title_lower'].isin(your_titles)]
                topic_papers = topic_papers.drop('title_lower', axis=1)
                
                print("\n" + "="*60)
                print(f"🎯 MOST CITED PAPERS: '{query}'")
                print("="*60)
                print(topic_papers[['title', 'year', 'citations', 'authors']].head(20).to_string(index=False))
                
                output_path = f"{output_dir}/discovered_topic_search.csv"
                topic_papers.to_csv(output_path, index=False)
                print(f"\n✓ Saved {len(topic_papers)} papers to {output_path}")
    
    print("\n" + "="*60)
    print("✅ DISCOVERY COMPLETE")
    print("="*60)
    print(f"Review discovered papers and add promising ones to Zotero")
    print(f"Results saved to {output_dir}/discovered_*.csv")


if __name__ == '__main__':
    main()
