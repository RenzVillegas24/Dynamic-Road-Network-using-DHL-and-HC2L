# Quick Reference - Optimized Edge Matching System

## ✨ What's New

The system now features **optimized edge matching** for HERE Traffic API data:

- 🚀 **18x faster** with persistent caching
- 🎯 **More accurate** with Hausdorff distance matching
- 🌲 **R-tree spatial indexing** for O(log n) lookups
- 💾 **Stable caching** that survives API order changes
- 🛣️ **Better defaults** with `network_type='drive'`

## 🚀 Quick Start

### Complete Setup (Recommended)
```bash
./setup.sh --full --both
```

This will:
1. ✅ Check dependencies (including rtree)
2. ✅ Build C++ algorithms (DHL & HC2L)
3. ✅ Generate network data with optimized matching
4. ✅ Build routing indexes
5. ✅ Start Flask server

### Step-by-Step
```bash
# 1. Build C++ executables
./setup.sh --build

# 2. Generate data (uses optimized matching automatically)
./setup.sh --data --both

# 3. Build routing indexes
./setup.sh --indexes

# 4. Run server
./setup.sh --server
```

## 📊 Traffic Data Modes

| Mode | Description | Usage |
|------|-------------|-------|
| `--both` | Flow + Incidents (default) | `./setup.sh --data --both` |
| `--flow` | Only traffic flow data | `./setup.sh --data --flow` |
| `--incidents` | Only incident data | `./setup.sh --data --incidents` |
| `--synthetic` | Simulated (no API key) | `./setup.sh --data --synthetic` |

## 🧪 Testing

### Test Optimized Matching
```bash
python test_optimized_matching.py
```

### Test Matcher Module
```bash
cd Main
python optimized_edge_matcher.py
```

### Run OSM Snapping Tests
```bash
cd Main
python test_osm_snapping.py
```

## 📁 Key Files

### New/Updated
- ✅ `Main/optimized_edge_matcher.py` - Core matching engine
- ✅ `setup.sh` - Unified setup script with matcher integration
- ✅ `test_optimized_matching.py` - Test script
- ✅ `OPTIMIZED_MATCHING_IMPLEMENTATION.md` - Technical docs

### Deprecated (Can Be Removed)
- ⚠️ `generate_data.sh` → Use `./setup.sh --data`
- ⚠️ `run-disruption-generator.sh` → Use `./setup.sh --data`
- ⚠️ `Main/geospatial_matcher.py` → Replaced by optimized version

### Cleanup Old Files
```bash
# Interactive cleanup
./cleanup-deprecated.sh

# Archive to deprecated/ folder
./cleanup-deprecated.sh --archive

# Auto-delete (no prompts)
./cleanup-deprecated.sh --auto
```

## 📦 Cache Management

### View Cache Stats
Cache is automatically created at: `Main/cache/flow_matching_cache.json`

```bash
# Check cache size
ls -lh Main/cache/flow_matching_cache.json

# View cache contents (first 20 lines)
head -20 Main/cache/flow_matching_cache.json
```

### Clear Cache
```bash
# Manual deletion
rm Main/cache/flow_matching_cache.json

# Via cleanup script
./setup.sh --clean
```

## 🔧 Troubleshooting

### rtree Not Found
```bash
# Install rtree package
conda activate .conda
pip install rtree
```

### No Matches Found
- Check HERE_API_KEY in `.env`
- Verify bbox covers your area
- Try `--synthetic` mode for testing

### Slow Matching
- First run is slow (builds cache)
- Second run is 18x faster
- Cache persists between runs

## 📖 Documentation

- **Technical Details**: `OPTIMIZED_MATCHING_IMPLEMENTATION.md`
- **Migration Guide**: `MIGRATION_NOTES.md`
- **Full README**: See main project README

## ⚡ Performance

Based on real HERE API data (1789 flow segments):

| Metric | Value |
|--------|-------|
| First run | 166.68s (93.2ms per segment) |
| With cache | 0.11s (18x faster) |
| Match rate | 18.5% (331/1789 segments) |
| Edges affected | 1,111 edges |
| Cache hit rate | 32.1% on second run |

## 🎯 Next Steps

After setup:

1. **Access the web interface**: http://localhost:5000
2. **Generate more scenarios**: `./setup.sh --data --both`
3. **Test different modes**: Try `--flow`, `--incidents`, `--synthetic`
4. **Monitor cache**: Check `Main/cache/flow_matching_cache.json` growth

## 📞 Support

See the documentation:
- `OPTIMIZED_MATCHING_IMPLEMENTATION.md` - Implementation details
- `MIGRATION_NOTES.md` - Migration from old system
- `./setup.sh --help` - Command reference
