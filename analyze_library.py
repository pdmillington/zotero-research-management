#!/usr/bin/env python3
"""
Analyze scored papers and generate reading lists
"""

import pandas as pd
import os
from config import OUTPUT_DIR, DEFAULT_CSV


def calculate_composite_score(df):
    """Calculate composite score from individual ratings"""
    
    # Only for papers that have at least one score
    scored = df[df['score'].notna() | df['quality'].notna()].copy()
    
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
    
    # Calculate composite (customize weights as needed)
    scored['composite'] = (
        scored['score'] * 0.5 +           # 50% relevance
        scored['quality'] * 0.3 +         # 30% quality
        scored['priority_num'] * 0.2      # 20% priority
    )
    
    return scored


def generate_reading_list(df, status_filter=None, top_n=20):
    """Generate prioritized reading list"""
    
    scored = calculate_composite_score(df)
    
    # Filter by status
    if status_filter:
        scored = scored[scored['status'] == status_filter]
    
    # Sort by composite score
    scored = scored.sort_values('composite', ascending=False)
    
    # Select columns for display
    display_cols = ['title', 'authors', 'year', 'journal', 
                   'score', 'quality', 'priority', 'composite', 'status']
    
    return scored[display_cols].head(top_n)


def papers_by_topic(df):
    """Group papers by topic"""
    
    # Expand topics (each paper can have multiple)
    topic_papers = []
    
    for idx, row in df.iterrows():
        if pd.notna(row['topics']):
            topics = [t.strip() for t in str(row['topics']).split(';')]
            for topic in topics:
                if topic:  # Skip empty
                    topic_papers.append({
                        'topic': topic,
                        'title': row['title'],
                        'authors': row['authors'],
                        'year': row['year'],
                        'score': row.get('score', None),
                        'composite': row.get('composite', None)
                    })
    
    df_topics = pd.DataFrame(topic_papers)
    
    # Group and count
    topic_counts = df_topics.groupby('topic').size().sort_values(ascending=False)
    
    return df_topics, topic_counts


def main():
    """Main analysis"""
    
    csv_path = f"{OUTPUT_DIR}/{DEFAULT_CSV}"
    
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"ERROR: {csv_path} not found!")
        print("Run fetch_library.py first")
        return
    
    print("="*80)
    print("ZOTERO LIBRARY ANALYSIS")
    print("="*80)
    
    # Overall statistics
    print(f"\nTotal papers: {len(df)}")
    scored_count = df['score'].notna().sum()
    print(f"Scored papers: {scored_count} / {len(df)} ({scored_count/len(df)*100:.1f}%)")
    
    if scored_count == 0:
        print("\nNo papers have been scored yet!")
        print("Add tags like 'score:5', 'quality:4', 'priority:high' in Zotero")
        return
    
    # Calculate composite scores
    df = calculate_composite_score(df)
    
    # Top papers overall
    print("\n" + "-"*80)
    print("TOP 10 PAPERS (by composite score)")
    print("-"*80)
    top_papers = generate_reading_list(df, top_n=10)
    print(top_papers.to_string(index=False))
    
    # Unread high-priority papers
    unread = df[df['status'].isin(['unread', 'skimmed']) | df['status'].isna()]
    if len(unread) > 0:
        print("\n" + "-"*80)
        print("READING LIST (unread/skimmed, highest priority)")
        print("-"*80)
        reading_list = calculate_composite_score(unread).sort_values('composite', ascending=False)
        display = reading_list[['title', 'authors', 'year', 'score', 'quality', 'priority', 'composite']].head(15)
        print(display.to_string(index=False))
    
    # Papers by topic
    print("\n" + "-"*80)
    print("PAPERS BY TOPIC")
    print("-"*80)
    df_topics, topic_counts = papers_by_topic(df)
    print("\nTopic counts:")
    print(topic_counts.head(15))
    
    # High-priority topics
    if 'composite' in df_topics.columns:
        print("\nTop papers by key topics:")
        for topic in topic_counts.head(5).index:
            topic_papers = df_topics[df_topics['topic'] == topic].sort_values('composite', ascending=False)
            print(f"\n{topic.upper()} (top 3):")
            for idx, paper in topic_papers.head(3).iterrows():
                print(f"  • {paper['title'][:60]} ({paper['year']}) - Score: {paper['composite']:.1f}")
    
    # Papers by year
    print("\n" + "-"*80)
    print("RECENT PAPERS (last 5 years, scored)")
    print("-"*80)
    current_year = pd.Timestamp.now().year
    recent = df[(df['year'].astype(str).str.isdigit()) & 
                (df['year'].astype(int) >= current_year - 5)]
    
    if len(recent) > 0:
        recent = recent.sort_values('composite', ascending=False)
        display = recent[['title', 'authors', 'year', 'composite']].head(10)
        print(display.to_string(index=False))
    
    print("\n" + "="*80)
    
    # Save reading list
    reading_list_path = f"{OUTPUT_DIR}/reading_list.csv"
    top_papers.to_csv(reading_list_path, index=False)
    print(f"\n✓ Reading list saved to {reading_list_path}")


if __name__ == '__main__':
    main()
