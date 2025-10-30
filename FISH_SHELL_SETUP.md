# Fish Shell Setup for VS Code

This guide helps you properly configure VS Code to work with Fish shell and the project's conda environment.

## Issue

When opening the terminal in VS Code, you see an error like:
```
source /home/renecuten/miniconda3/bin/activate ...
~/miniconda3/bin/activate (line 2): Unsupported use of '='. In fish, please use 'set _CONDA_ROOT ...'
```

This happens because conda's default `activate` script uses bash syntax, but VS Code's terminal is using Fish shell.

## Solution

### Step 1: Verify VS Code Settings

The `.vscode/settings.json` file has been configured to:
- Set Fish as the default terminal shell
- Point Python to the project's conda environment
- Properly handle conda environment variables

### Step 2: Manual Activation (Quick Fix)

If you want to quickly activate the environment in the terminal, use:

```fish
# Initialize conda for fish (one time)
source (conda info --base)/etc/fish/conf.d/conda.fish

# Activate the project environment
conda activate .conda
```

### Step 3: Use Helper Functions

The `.vscode/fish_init.fish` file provides useful shortcuts. To use them, source it in your terminal:

```fish
source .vscode/fish_init.fish
```

Then you can use these commands:

```fish
# Activate the conda environment
activate_project_env

# Generate OSM data
gen_data

# Generate indexes
gen_indexes

# Build all executables
build_all

# Start the server
run_server
```

### Step 4: Add to Fish Config (Optional - for permanent setup)

To automatically load these functions every time you start Fish, add this to your Fish config file (`~/.config/fish/config.fish`):

```fish
# Load project environment if in the project directory
if test -f .vscode/fish_init.fish
    source .vscode/fish_init.fish
end
```

## Workflow

The recommended workflow in VS Code with Fish shell:

```fish
# 1. Open terminal (Ctrl+`)
# The .vscode/settings.json ensures Fish is used

# 2. Activate the environment
conda activate .conda

# 3. Generate data (if needed)
cd Main
python request_new_datasets.py

# 4. Generate indexes
cd ..
./generate_indexes.sh

# 5. Run the server
./run_server.fish
```

Or use the helper script:

```fish
source .vscode/fish_init.fish
gen_data
gen_indexes
run_server
```

## Troubleshooting

### Still seeing the bash error?

Try restarting VS Code completely:
1. Close all VS Code windows
2. Kill any remaining `code` processes: `killall code`
3. Reopen the project

### Conda not found?

Make sure conda is installed and in your PATH:
```fish
which conda
conda --version
```

If not found, check your Fish config file (`~/.config/fish/config.fish`) to ensure conda initialization is there.

### Python interpreter not recognized?

Run this in VS Code's Python terminal:
```fish
which python
python --version
```

If the path doesn't show `.conda/bin/python`, try:
```fish
conda activate .conda
which python
```

## Files Created/Modified

- `.vscode/settings.json` - VS Code terminal and Python configuration
- `.vscode/launch.json` - Debug configurations for Flask
- `.vscode/fish_init.fish` - Fish shell helper functions
