#!/usr/bin/env fish
# Master launcher - Start Flask server AND auto-disruption generator together
# This ensures real-time dynamic disruptions during route navigation

set SCRIPT_DIR (dirname (realpath (status --current-filename)))
cd $SCRIPT_DIR

echo "════════════════════════════════════════════════════════════════"
echo "🚀 Dynamic Road Network System - Master Launcher"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Starting services:"
echo "  1. Dynamic Disruption Generator (90s interval)"
echo "  2. Flask Web Server (with auto-route updates)"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""

# Kill any existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f "dynamic_disruption_generator.py" 2>/dev/null
pkill -f "flask_server.py" 2>/dev/null
sleep 2

# Start disruption generator in background
echo "🔄 Starting disruption generator (background)..."
python dynamic_disruption_generator.py --interval 90 --intensity medium > disruption_generator.log 2>&1 &
set DISRUPTION_PID $last_pid
echo "   PID: $DISRUPTION_PID"
echo "   Log: disruption_generator.log"
sleep 2

# Start Flask server
echo "🌐 Starting Flask server..."
echo "   URL: http://localhost:5000"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ System Ready!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Features enabled:"
echo "  ✓ Real-time disruption updates (every 90 seconds)"
echo "  ✓ Automatic route recalculation when disruptions change"
echo "  ✓ Both DHL and LazyHC2L algorithms"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Function to cleanup on exit
function cleanup
    echo ""
    echo "🛑 Shutting down services..."
    echo "   Stopping disruption generator (PID: $DISRUPTION_PID)..."
    kill $DISRUPTION_PID 2>/dev/null
    echo "   Stopping Flask server..."
    # Flask will stop automatically when this script exits
    echo "✅ Cleanup complete"
    exit 0
end

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Start Flask (foreground)
python flask_server.py
