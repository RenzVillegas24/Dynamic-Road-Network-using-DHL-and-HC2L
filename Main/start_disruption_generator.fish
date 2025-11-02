#!/usr/bin/env fish
# Start Dynamic Disruption Generator
# Generates random road disruptions periodically for realistic simulation

set SCRIPT_DIR (dirname (realpath (status --current-filename)))
cd $SCRIPT_DIR

# Default values
set interval 30
set intensity "medium"
set mode "continuous"

# Parse arguments
set i 1
while test $i -le (count $argv)
    switch $argv[$i]
        case --interval -i
            set i (math $i + 1)
            set interval $argv[$i]
        case --intensity -n
            set i (math $i + 1)
            set intensity $argv[$i]
        case --once -o
            set mode "once"
        case --help -h
            echo "Usage: start_disruption_generator.fish [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --interval, -i <seconds>    Update interval (default: 30)"
            echo "  --intensity, -n <level>     Intensity: low, medium, high, extreme (default: medium)"
            echo "  --once, -o                  Generate once and exit"
            echo "  --help, -h                  Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./start_disruption_generator.fish                    # Run with defaults (30s, medium)"
            echo "  ./start_disruption_generator.fish -i 60 -n high     # Update every 60s, high intensity"
            echo "  ./start_disruption_generator.fish --once            # Generate once"
            exit 0
    end
    set i (math $i + 1)
end

echo "================================"
echo "Dynamic Disruption Generator"
echo "================================"
echo "Mode: $mode"
echo "Interval: $interval seconds"
echo "Intensity: $intensity"
echo ""

if test $mode = "once"
    python dynamic_disruption_generator.py --once --intensity $intensity
else
    python dynamic_disruption_generator.py --interval $interval --intensity $intensity
end
