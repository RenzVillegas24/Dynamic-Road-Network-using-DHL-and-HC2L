#!/bin/bash
# Quick Reference - Hash-Based Traffic System
# ============================================

cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════╗
║              Dynamic Road Network - Quick Reference                ║
║              Hash-Based Traffic Matching System                    ║
╚═══════════════════════════════════════════════════════════════════╝

🚀 ONE COMMAND TO RULE THEM ALL:
   ./setup.sh --full           # Build everything + run server

📋 Common Tasks:
   ./setup.sh --build          # Build C++ algorithms only
   ./setup.sh --data --flow    # Generate traffic data (flow only)
   ./setup.sh --server         # Start Flask server

🌐 Traffic Data Modes:
   --flow      Traffic flow data only (default)
   --both      Flow + incidents
   --incidents Incidents only

⚡ What Changed (Hash-Based System):
   ✅ 90x faster matching (hash lookup vs geospatial)
   ✅ Auto-fetches traffic every 90s in background
   ✅ Symlinks always point to latest data
   ✅ No manual data generation needed

📁 Traffic Files (Auto-Updated):
   Main/data/disruptions/current_traffic_flow.gr    → Latest flow data
   Main/data/disruptions/current_traffic_both.gr    → Latest flow + incidents
   Main/data/disruptions/traffic_<timestamp>_*.gr   → Historical snapshots

🔧 Helper Script (Manual Traffic Fetch):
   ./generate_traffic.fish flow          # One-time fetch
   ./generate_traffic.fish both --live   # Continuous (60s)

📊 Core Files:
   Main/here_osm/matched_edges.csv       → 732 traffic hashes → 2,901 OSM edges
   Main/traffic_hash_matcher.py          → Hash-based matcher
   Main/realtime_traffic_service.py      → Traffic service
   unified_data_generator_v2.py          → CLI interface

🗑️  Deprecated (Renamed to *.old):
   unified_data_generator.py             → Old version (slow)
   Main/here_traffic_service.py          → Old version
   Main/optimized_edge_matcher.py        → Geospatial matching

🎯 Quick Start:
   1. ./setup.sh --build                 # Build C++ (once)
   2. ./setup.sh --data --flow           # Fetch traffic data
   3. ./setup.sh --server                # Start server (auto-updates)

Server automatically fetches traffic every 90 seconds!
No manual refresh needed. ✨

EOF
