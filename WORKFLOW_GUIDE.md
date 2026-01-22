# Zotero Research Tools - Workflow Guide

## File Priority System (UPDATED)

All analysis and discovery tools now use this smart priority:

1. **Fresh Export** (`library_export.csv`) - Default
   - Contains your latest tags/scores from Zotero
   - Created by: `fetch_library.py` or `fetch_library_with_collections.py`
   - Fast to generate (30-60 seconds)

2. **Citations File** (`library_with_citations.csv`) - Optional Enhancement
   - Only used if it's NEWER than fresh export
   - Contains Semantic Scholar IDs and citation counts
   - Created by: `add_citations.py`
   - Slow to generate (6-10 minutes for 126 papers)

### Smart Logic:
```
IF citations file exists AND is newer than export:
    → Use citations file (has both fresh data + citations)
ELSE:
    → Use fresh export (has current scores)
```

---

## Daily Workflow (Fast - No Citations Needed)

### 1. Update Tags in Zotero
- Score papers: `score:1-5`
- Set priority: `priority:high/medium/low`
- Set status: `status:unread/read/skimmed`
- Add topics: `topic:market-structure`, etc.

### 2. Fetch Fresh Data
```bash
# Without collections (fast - 30 sec)
python fetch_library.py

# With collections (slower - 2-5 min, but has collection data)
python fetch_library_with_collections.py
```

### 3. Analyze Immediately
```bash
# Analyze entire library
python analyze_library_enhanced.py

# Analyze specific collections
python analyze_collections.py
```

**Result:** Instant analysis with your latest scores!

---

## Weekly/Monthly Workflow (With Citations)

### When to Update Citations:
- ✅ After adding many new papers
- ✅ Before grant proposals (need citation metrics)
- ✅ Monthly/quarterly reviews
- ❌ NOT after every tag update (too slow!)

### Process:
```bash
# 1. Fetch fresh data
python fetch_library_with_collections.py

# 2. Add citations (slow - run overnight or during lunch)
python add_citations.py
# OR for large libraries:
python add_citations_batch.py

# 3. Now all tools automatically use citation-enhanced data
python analyze_library_enhanced.py
python analyze_collections.py
python discover_papers.py
python discover_collections.py
```

**Result:** Analysis includes citation percentiles, hidden gems, etc.

---

## File Lifecycle Example

### Scenario 1: Quick Daily Use
```
Monday 9am:  Update 10 paper scores in Zotero
Monday 9:05am: Run fetch_library.py → library_export.csv (created/updated)
Monday 9:06am: Run analyze_library_enhanced.py
             → Uses library_export.csv ✓
             → Shows your new scores ✓
```

### Scenario 2: Weekly Citation Update
```
Friday 5pm:  Run fetch_library.py → library_export.csv (updated)
Friday 5:01pm: Run add_citations.py → library_with_citations.csv (updated)
Friday 5:08pm: Run analyze_library_enhanced.py
             → library_with_citations.csv is newer ✓
             → Uses citation-enhanced file ✓
             → Analysis includes citation data ✓

Monday 9am:  Update scores in Zotero
Monday 9:05am: Run fetch_library.py → library_export.csv (updated)
Monday 9:06am: Run analyze_library_enhanced.py
             → library_export.csv is now newer (Monday > Friday)
             → Uses fresh export with new scores ✓
             → Citation data not available (but that's OK - scores are current)
```

---

## Which Tool Needs What?

| Tool | Requires Fresh Export | Can Use Citations | Needs SS IDs |
|------|----------------------|-------------------|--------------|
| `fetch_library.py` | Creates it | - | - |
| `fetch_library_with_collections.py` | Creates it | - | - |
| `add_citations.py` | Yes (to update) | Creates it | Creates them |
| `analyze_library_enhanced.py` | Yes | Optional | No |
| `analyze_collections.py` | Yes | Optional | No |
| `discover_papers.py` | Yes | Not needed | **YES** |
| `discover_collections.py` | Yes | Not needed | **YES** |

**Key Insight:** 
- **Analysis tools** work fine without citations (just missing citation-aware features)
- **Discovery tools** need Semantic Scholar IDs (must run `add_citations.py` at least once)

---

## Best Practices

### ✅ DO:
- Update Zotero tags frequently (instant)
- Run `fetch_library.py` after tag updates (30 sec)
- Run `add_citations.py` monthly or before important analysis (6-10 min)
- Keep `library_export.csv` as your "current working file"

### ❌ DON'T:
- Re-run citations after every small Zotero update
- Worry if analysis doesn't show citations (scores are more important)
- Delete old citation files (they're backups of SS IDs)

---

## Troubleshooting

### "My new scores aren't showing up!"
```bash
# 1. Check what you last ran
ls -lt data/*.csv | head -3

# 2. See which file is newest
# If library_with_citations.csv is older than your Zotero updates:

# 3. Either re-run citations:
python add_citations.py

# OR just fetch fresh export (tool will use it automatically):
python fetch_library.py
python analyze_library_enhanced.py  # Will use fresh export
```

### "Discovery tools say 'No Semantic Scholar IDs found'"
```bash
# Run citations at least once to get SS IDs:
python add_citations.py

# SS IDs persist in library_with_citations.csv
# Even if this file is "older", discovery tools can still use the SS IDs
```

### "I want to force use of fresh export"
```bash
# Delete or rename the citations file temporarily:
mv data/library_with_citations.csv data/library_with_citations.csv.backup

# Now all tools will use fresh export:
python analyze_library_enhanced.py
```

---

## File Timestamps Matter!

The tools compare file modification times:
```python
if citations_file_time > export_file_time:
    use_citations_file()
else:
    use_fresh_export()
```

**This means:**
- After running `fetch_library.py`, that file becomes "newest"
- Tools automatically switch to using it (with your current scores)
- Until you run `add_citations.py` again, which creates a newer citations file

---

## Summary

**The New Smart System:**
1. Tag papers in Zotero (instant)
2. Run `fetch_library.py` (30 sec) 
3. Run analysis (instant, uses fresh scores)
4. Occasionally run `add_citations.py` (slow but rare)

**Result:** Fast daily workflow, with optional monthly citation enhancement!
