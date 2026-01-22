#!/usr/bin/env python3
"""
Enhanced library analysis with citation-aware prioritization
"""

import pandas as pd
import numpy as np
import os
from config import OUTPUT_DIR, DEFAULT_CSV


def calculate_citation_percentile(df):
    """Calculate citation percentile for each paper"""
    
    if 'citations' not in df.columns:
        print("Warning: No citation data found. Run add_citations.py first.")
        df['citation_percentile'] = 50  # Default to median
        return df
    
    papers_with_citations = df[df['citations'].notna()].copy()
    
    if len(papers_with_citations) == 0:
        df['citation_percentile'] = 50
        return df
    
    # Calculate percentile rank (0-100)
    df['citation_percentile'] = df['citations'].rank(pct=True) * 100
    
    # Fill missing with median
    df['citation_percentile'] = df['citation_percentile'].fillna(50)
    
    return df


def calculate_composite_score(df, use_citations=True):
    """
    Calculate composite score from individual ratings
    
    Modes:
    - use_citations=True: Include citation impact in scoring
    - use_citations=False: Use only your personal ratings
    """
    
    # Only for papers that have at least one score
    scored = df[df['score'].notna() | df['quality'].notna()].copy()
    
    if len(scored) == 0:
        print("No scored papers found!")
        return pd.DataFrame()
    
    # Fill missing scores with median
    if 'score' in scored.columns:
        scored['score'] = scored['score'].fillna(scored['score'].median())
    else:
        scored['score'] = 3
        
    if 'quality' in scored.columns:
        scored['quality'] = scored['quality'].fillna(scored['quality'].median())
    else:
        scored['quality'] = 3
    
    # Map priority to numeric
    priority_map = {'high': 3, 'medium': 2, 'low': 1}
    scored['priority_num'] = scored['priority'].map(priority_map).fillna(2)
    
    # Calculate citation percentile
    scored = calculate_citation_percentile(scored)
    
    # Normalize citation percentile to 1-5 scale
    scored['citation_score'] = (scored['citation_percentile'] / 100) * 4 + 1  # Maps 0-100 to 1-5
    
    if use_citations and 'citations' in scored.columns and scored['citations'].notna().any():
        # CITATION-AWARE COMPOSITE SCORE
        scored['composite'] = (
            scored['score'] * 0.35 +           # 35% relevance to your work
            scored['quality'] * 0.25 +         # 25% methodological quality
            scored['priority_num'] * 0.15 +    # 15% urgency/priority
            scored['citation_score'] * 0.25    # 25% field impact (citations)
        )
        print("\n✓ Using citation-aware scoring")
    else:
        # PERSONAL SCORING ONLY
        scored['composite'] = (
            scored['score'] * 0.5 +            # 50% relevance
            scored['quality'] * 0.3 +          # 30% quality
            scored['priority_num'] * 0.2       # 20% priority
        )
        print("\n✓ Using personal scoring only")
    
    return scored


def find_hidden_gems(df, top_n=20):
    """
    Find highly-cited papers you haven't rated yet
    These might be important papers you've overlooked
    """
    
    if 'citations' not in df.columns or df['citations'].isna().all():
        print("\nNo citation data available for hidden gem detection")
        return pd.DataFrame()
    
    # Papers with citations but no score
    unscored = df[df['score'].isna() & df['citations'].notna()].copy()
    
    if len(unscored) == 0:
        print("\nNo unscored papers with citation data")
        return pd.DataFrame()
    
    # Calculate percentile among ALL papers
    df_temp = calculate_citation_percentile(df)
    unscored = df_temp[df_temp['score'].isna() & df_temp['citations'].notna()].copy()
    
    # Find papers in top quartile of citations
    high_impact = unscored[unscored['citation_percentile'] >= 75].copy()
    
    if len(high_impact) == 0:
        print("\nNo highly-cited unscored papers found")
        return pd.DataFrame()
    
    # Sort by citations
    high_impact = high_impact.sort_values('citations', ascending=False)
    
    return high_impact.head(top_n)


def find_citation_outliers(df):
    """
    Find papers where YOUR rating disagrees with citation impact
    
    Two types:
    1. You rated low, but highly cited (might need re-evaluation)
    2. You rated high, but few citations (niche but valuable to you)
    """
    
    if 'citations' not in df.columns or df['citations'].isna().all():
        print("\nNo citation data for outlier detection")
        return None, None
    
    scored = df[(df['score'].notna()) & (df['citations'].notna())].copy()
    
    if len(scored) < 10:
        print("\nNeed more scored papers with citations for outlier detection")
        return None, None
    
    scored = calculate_citation_percentile(scored)
    
    # Normalize both to 0-1 scale
    scored['score_norm'] = (scored['score'] - 1) / 4  # 1-5 -> 0-1
    scored['citation_norm'] = scored['citation_percentile'] / 100  # 0-100 -> 0-1
    
    # Calculate disagreement
    scored['disagreement'] = scored['citation_norm'] - scored['score_norm']
    
    # Type 1: High citations, low your score (disagreement > 0.3)
    underrated = scored[scored['disagreement'] > 0.3].sort_values('disagreement', ascending=False)
    
    # Type 2: Low citations, high your score (disagreement < -0.3)
    niche_gems = scored[scored['disagreement'] < -0.3].sort_values('disagreement', ascending=True)
    
    return underrated.head(10), niche_gems.head(10)


def generate_reading_list(df, status_filter=None, top_n=20, use_citations=True):
    """Generate prioritized reading list"""
    
    scored = calculate_composite_score(df, use_citations=use_citations)
    
    if len(scored) == 0:
        return pd.DataFrame()
    
    # Filter by status
    if status_filter:
        scored = scored[scored['status'] == status_filter]
    
    # Sort by composite score
    reading_list = scored.sort_values('composite', ascending=False)
    
    # Select columns to display
    display_cols = ['title', 'year', 'score', 'quality', 'priority', 'composite']
    
    if 'citations' in reading_list.columns:
        display_cols.insert(5, 'citations')
    
    if 'topics' in reading_list.columns:
        display_cols.append('topics')
    
    available_cols = [c for c in display_cols if c in reading_list.columns]
    
    return reading_list[available_cols].head(top_n)


def analyze_by_topic(df, use_citations=True):
    """Analyze top papers by research topic"""
    
    if 'topics' not in df.columns:
        print("\nNo topic tags found")
        return
    
    scored = calculate_composite_score(df, use_citations=use_citations)
    
    if len(scored) == 0:
        return
    
    # Get papers with topics
    with_topics = scored[scored['topics'].notna()].copy()
    
    if len(with_topics) == 0:
        print("\nNo papers with topic tags")
        return
    
    # Split topics (semicolon separated)
    with_topics['topic_list'] = with_topics['topics'].str.split(';')
    
    # Explode to one row per topic
    exploded = with_topics.explode('topic_list')
    exploded['topic_list'] = exploded['topic_list'].str.strip()
    
    # Group by topic
    topic_groups = exploded.groupby('topic_list').agg({
        'composite': ['mean', 'count'],
        'citations': ['mean', 'sum'] if 'citations' in exploded.columns else ['count']
    }).round(2)
    
    topic_groups.columns = ['_'.join(col).strip() for col in topic_groups.columns]
    topic_groups = topic_groups.sort_values('composite_mean', ascending=False)
    
    print("\n" + "="*60)
    print("TOP TOPICS BY AVERAGE COMPOSITE SCORE")
    print("="*60)
    print(topic_groups.head(10))
    
    # Top papers per major topic
    major_topics = topic_groups.head(5).index
    
    for topic in major_topics:
        papers = exploded[exploded['topic_list'] == topic].sort_values('composite', ascending=False)
        print(f"\n{'='*60}")
        print(f"TOP PAPERS: {topic}")
        print(f"{'='*60}")
        
        display_cols = ['title', 'year', 'composite']
        if 'citations' in papers.columns:
            display_cols.append('citations')
        
        available_cols = [c for c in display_cols if c in papers.columns]
        print(papers[available_cols].head(5).to_string(index=False))


def main():
    """Main analysis workflow"""
    
    # Use fresh export by default (has current scores from Zotero)
    csv_path = f"{OUTPUT_DIR}/{DEFAULT_CSV}"
    
    # Check if citations file exists and is newer (optional enhancement)
    citations_path = f"{OUTPUT_DIR}/library_with_citations.csv"
    
    if os.path.exists(citations_path) and os.path.exists(csv_path):
        # Use whichever is more recent
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
        print("Run fetch_library.py first")
        return
    
    has_citations = 'citations' in df.columns and df['citations'].notna().any()
    
    print("\n" + "="*60)
    print("ZOTERO LIBRARY ANALYSIS")
    print("="*60)
    print(f"Total papers: {len(df)}")
    print(f"Scored papers: {df['score'].notna().sum()}")
    print(f"With citations: {df['citations'].notna().sum() if has_citations else 0}")
    print(f"Unread papers: {(df['status'] == 'unread').sum() if 'status' in df.columns else 'unknown'}")
    
    # 1. OVERALL READING LIST (Citation-aware)
    print("\n" + "="*60)
    print("📚 TOP PRIORITY READING LIST (Citation-Aware)")
    print("="*60)
    reading_list = generate_reading_list(df, top_n=15, use_citations=has_citations)
    if len(reading_list) > 0:
        print(reading_list.to_string(index=False))
    
    # 2. UNREAD ONLY
    if 'status' in df.columns:
        print("\n" + "="*60)
        print("📖 TOP UNREAD PAPERS")
        print("="*60)
        unread_list = generate_reading_list(df, status_filter='unread', top_n=15, use_citations=has_citations)
        if len(unread_list) > 0:
            print(unread_list.to_string(index=False))
        else:
            print("No unread papers found")
    
    # 3. HIDDEN GEMS (Highly cited but unscored)
    if has_citations:
        print("\n" + "="*60)
        print("💎 HIDDEN GEMS (Highly cited, but you haven't rated)")
        print("="*60)
        gems = find_hidden_gems(df, top_n=15)
        if len(gems) > 0:
            display_cols = ['title', 'year', 'citations', 'citation_percentile']
            available_cols = [c for c in display_cols if c in gems.columns]
            print(gems[available_cols].to_string(index=False))
            print(f"\n💡 Suggestion: Review these {len(gems)} papers - they're highly influential in your library")
        else:
            print("No hidden gems found - you've scored all highly-cited papers!")
    
    # 4. OUTLIERS (Your rating vs citations)
    if has_citations:
        print("\n" + "="*60)
        print("🔍 RATING vs CITATIONS OUTLIERS")
        print("="*60)
        
        underrated, niche = find_citation_outliers(df)
        
        if underrated is not None and len(underrated) > 0:
            print("\n⚠️  Papers you rated LOW but are HIGHLY CITED:")
            print("(Consider re-reading - might be more important than you thought)\n")
            cols = ['title', 'year', 'score', 'citations', 'citation_percentile']
            available = [c for c in cols if c in underrated.columns]
            print(underrated[available].to_string(index=False))
        
        if niche is not None and len(niche) > 0:
            print("\n⭐ Papers you rated HIGH but have FEW CITATIONS:")
            print("(Niche gems - valuable to you but not mainstream)\n")
            cols = ['title', 'year', 'score', 'citations']
            available = [c for c in cols if c in niche.columns]
            print(niche[available].to_string(index=False))
    
    # 5. TOPIC ANALYSIS
    if 'topics' in df.columns:
        analyze_by_topic(df, use_citations=has_citations)
    
    # 6. SUMMARY STATS
    if has_citations:
        scored_with_cites = df[(df['score'].notna()) & (df['citations'].notna())]
        if len(scored_with_cites) > 0:
            print("\n" + "="*60)
            print("📊 CITATION STATISTICS (Your Scored Papers)")
            print("="*60)
            print(f"Total citations: {scored_with_cites['citations'].sum():.0f}")
            print(f"Average citations: {scored_with_cites['citations'].mean():.1f}")
            print(f"Median citations: {scored_with_cites['citations'].median():.0f}")
            print(f"Most cited: {scored_with_cites['citations'].max():.0f}")
            
            # Citation by your score
            by_score = scored_with_cites.groupby('score')['citations'].agg(['mean', 'count'])
            print("\nAverage citations by YOUR score:")
            print(by_score.round(1))


if __name__ == '__main__':
    main()
