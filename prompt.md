# Experiment Runner Backend Migration & Multi-threading Implementation

## Overview
Implement server-side experiment runner with multi-threading capabilities for large-scale performance testing. Frontend becomes display-only interface consuming pre-calculated results from Python backend.

## Core Architecture Changes

### Server-Side Processing
- Move ALL experiment execution logic to Python backend
- Frontend becomes display-only interface consuming server results
- Results stored as files on disk, NOT in RAM/browser memory
- Python backend handles ALL parsing and calculations
- Frontend only renders pre-calculated data from backend

### File Structure & Caching

#### Experiment Storage Structure
```
Main/data/experiments/
├── preset/                          # Preset experiment configurations (permanent)
│   ├── ExperimentPreset.json       # Preset experiment metadata
│   ├── disruptions/                # Preset disruption sets
│   │   └── set_batch_*_route_*/
│   │       ├── flow/               # Flow disruption files
│   │       └── incidents/          # Incident disruption files
│   └── results/                     # Preset experiment results
│       └── [experiment_id]/
│           ├── progress.json       # Real-time progress tracking
│           └── result_*.json       # Individual route results
├── temporary/                       # Temporary experiment runs (auto-cleanup)
│   ├── [temporary_id]/             # Temporary experiment folder
│   │   ├── disruptions/            # Generated disruption sets
│   │   │   └── set_trial_*_route_*/
│   │   │       ├── flow/
│   │   │       └── incidents/
│   │   └── results/
│   │       ├── progress.json
│   │       └── result_*.json
│   └── [experiment_config].json    # Temporary experiment config
```

#### Results Storage
- Preset experiments: `Main/data/experiments/preset/results/[experiment_id]/`
- Temporary experiments: `Main/data/experiments/temporary/results/[experiment_id]/`
- Each experiment gets its own folder with progress tracking
- Progress tracking file: `progress.json` inside each results folder
- Each CPP API run result saved as separate JSON file in results folder
- Progress file tracks ALL threaded tasks with individual progress metrics
- Cache cleared automatically on stop/finish operations

#### Progress Tracking Format
The `progress.json` file must contain for EACH trial or trial-batch combination:

**Demo Running Status:**
- Demo name with timestamp
- Current status message (e.g., "Computing route with DHL...")
- Overall progress percentage across all threads

**Per-Thread Progress Metrics:**
- Thread ID and progress percentage
- Trial number (format: X/Y)
- Route progress (format: X/Y, e.g., "3/25")
- Algorithm being used (e.g., "DHL")
- Thread status (running/paused/completed/error)
- Current disruption being processed

**Last Result (per thread):**
- Route details (Origin → Destination)
- Algorithm used
- Query Time (ms)
- Distance (km)
- Baseline ETA
- Actual ETA
- Time Impact (seconds)
- Label Size

**Update Phase (per thread):**
- Lazy Update Time (ms)
- Max Label Size
- Min Label Size
- Nodes Repaired (HC2L only)
- Dirty Nodes (HC2L only)
- Impact Score

**Query Phase (per thread):**
- Algorithm identifier
- Avg Query Time (ms)
- Min Query Time (ms)
- Max Query Time (ms)
- Std Dev
- Queries Count

**Results History (per thread):**
- Total results count
- Highlights only (limited to recent/significant results)

**Disruption Display (shared across threads):**
- Show Incidents toggle state
- Show Flow toggle state
- Current disruptions being processed
- Total disruptions count

**Overall Progress Metrics:**
- Combined route progress across all threads
- Overall completion percentage
- Estimated time remaining
- Routes completed / Total routes

### Tracking System
Track experiment progress with these components:
- Demo Name & Status Card data
- Overall Progress across all threads
- Per-thread Trial/Batch identification
- Per-thread Route progress
- Per-thread Algorithm
- Per-thread Last Result (complete metrics)
- Per-thread Update Phase (complete metrics)
- Per-thread Query Phase (complete metrics)
- Per-thread Results History (highlights only)
- Current run mode details (normal/experiment)
- All threaded task progress with complete metrics

## API Routes

### Required Endpoints
```
POST   /api/experiment/start           # Start new experiment run
POST   /api/experiment/[id]/pause      # Pause running experiment
POST   /api/experiment/[id]/stop       # Stop running experiment
POST   /api/experiment/[id]/resume     # Resume paused experiment
GET    /api/experiment/[id]/progress   # Get current progress (HTTP polling fallback)
GET    /api/experiment/[id]/result     # Get final results
WS     /api/experiment/[id]/status     # WebSocket for real-time updates
POST   /api/experiment/preset/list     # List all preset experiments
GET    /api/experiment/preset/metadata # Get preset metadata
POST   /api/experiment/cleanup         # Clean up temporary experiments
```

### WebSocket Implementation
- Use WebSocket for real-time status updates
- Endpoint: `/api/experiment/[id]/status`
- Enables live progress tracking without polling
- Push `progress.json` updates to all connected clients in real-time
- Update frequency: push on every route completion or significant progress change
- Include delta updates to minimize bandwidth usage for large experiments
- Connection message includes demo_id for client-side routing
- On disconnection, state persists in `progress.json` for reconnection recovery

## Multi-threading Configuration

### Automatic Detection
- Detect task size automatically based on:
  - Number of routes to process
  - Number of disruption files
  - Number of algorithms
  - Number of trials
- Enable multi-threading for large tasks (threshold: 100+ routes or 500+ disruption files)
- Use single thread for minimal tasks (threshold: <100 routes)
- Add toggle for manual multi-threading override
- Display recommendation to user when auto-detection triggers

### Experiment Multi-threading (Default: ON for preset experiments)
**Context:** 2 algorithms × 3 trials × 3 batches × 1000 disruption files = 18,000 total files (3,000 unique disruptions)

**Threading Options:**
1. **Default (Recommended):** 3 trial threads (one per trial)
   - Simpler to track
   - Lower memory overhead
   - Easier debugging
   
2. **Advanced:** 9 threads (3 trials × 3 batches each)
   - Faster completion for large experiments
   - Higher memory usage
   - Requires sufficient system resources

**Thread Count Selection Logic:**
- Use default 3-thread approach unless:
  - System has 8+ CPU cores
  - Available RAM > 8GB
  - User manually selects 9-thread mode
- Monitor system resources during execution
- Dynamically reduce threads if resource exhaustion detected

### Config Multi-threading
- Auto-enable only when task size exceeds threshold
- Single thread for simple configurations (<100 routes)
- Multi-threading for complex/large configurations (100+ routes)
- User can override auto-detection via toggle

## Display Behavior

### Single Thread Mode
- Zoom and follow current route on map
- Standard route visualization with single path highlighted
- Focus on individual process
- Show single progress section with:
  - Overall Progress bar
  - Trial/Route/Algorithm indicators
  - Last Result metrics card
  - Update Phase metrics card
  - Query Phase metrics card
  - Results History section with highlights
- Map centered on current route being processed

### Multi-thread Mode
- **NO** automatic zooming to individual routes
- View centered on Quezon City at all times (fixed center point)
- Display ALL routes simultaneously from multiple threads (different colors per thread)
- Show comprehensive details in `demo-runner-tab-running`
- Group results by trial and batch with collapsible sections
- Visualize multiple concurrent processes with color-coded routes
- Display individual progress sections for EACH thread showing:
  - Thread identifier (Trial X/Y or Trial X Batch Y/Z)
  - Thread-specific progress bar
  - Route progress (current/total)
  - Algorithm being used
  - Last Result (all metrics)
  - Update Phase (all metrics)
  - Query Phase (all metrics)
  - Results History (highlights)
- Each thread gets its own collapsible/expandable section
- Shared Disruption Display at top level
- Color legend showing which color corresponds to which thread
- Option to temporarily highlight/zoom specific thread by clicking its section

## Frontend Changes

### New Experiment Runner Implementation
- Create entirely NEW experiment runner file: `experiment-runner.js`
- Create entirely NEW experiment panel HTML: `experiment-runner-panel.html`
- New runner uses WebSocket connections to backend exclusively
- Remove ALL client-side computation logic
- Transfer necessary utility functions from legacy code
- Read and display progress from `progress.json` file via WebSocket updates
- Render per-thread progress sections dynamically based on active thread count
- Group and display all metrics per thread
- Implement color-coding system for multi-thread route visualization
- Add thread selection/highlighting functionality

### Experiment Creator/Preset Manager
- Create `experiment-preset-manager.js` for managing preset experiments
- Load preset configuration from `ExperimentPreset.json`
- Display available preset experiments
- Allow creation of temporary experiments (on-demand runs)
- Validate preset structure on load
- Handle disruption metadata display without loading full files
- Support batch/trial selection for partial runs

## Experiment Initialization & Disruption Management

### ExperimentPreset.json Setup
- Create `ExperimentPreset.json` at `Main/data/experiments/preset/`
- Contains permanent preset experiment configuration:
  - Experiment ID (unique identifier)
  - Experiment name and description
  - Algorithm list (e.g., ['DHL', 'HC2L'])
  - Trial count (e.g., 3)
  - Batch count (e.g., 3)
  - Disruption configuration:
    - Total disruption sets
    - Batch structure (sets per batch)
    - Pre-generated flag (whether disruptions already exist)
  - Creation timestamp
  - Last modified timestamp
- Validate configuration on load at startup
- Support multiple preset experiments (one main, extendable for others)

### Temporary Experiment Configuration
- Generate temporary config ID on experiment start
- Save minimal config to `Main/data/experiments/temporary/[temp_id].json`
- Include:
  - Temporary experiment ID
  - Parent preset ID (if based on preset)
  - Custom parameters (overrides)
  - Creation timestamp
  - Thread count selection
- Auto-cleanup temporary configs after experiment completion

### Disruption File Generation & Management

#### Preset Disruption Structure
- Disruptions pre-generated and stored at `Main/data/experiments/preset/disruptions/`
- Named: `set_batch_0_route_0/`, `set_batch_0_route_1/`, etc.
- Organized by batch and route for batch-level parallelization
- Disruption files (flow and incidents) pre-exist or generated on first use

#### Temporary Disruption Generation
- For temporary experiments: generate in `Main/data/experiments/temporary/[temp_id]/disruptions/`
- Named: `set_trial_0_route_0/`, `set_trial_1_route_0/`, etc. (trial-based for trial threading)
- Use lazy generation: only create when needed by active thread
- Generate in 10-chunk batches per task/thread
- Prevents memory overload during generation
- Show generation progress in UI
- Log generation statistics for debugging

#### Disruption Cache Management

**Lazy Loading Strategy:**
- Load disruptions only when needed by processing thread
- Process in 10-chunk batches per task (chunk size: 100 disruption files)
- Reduces initial memory footprint
- Pre-load next chunk when current chunk 80% processed
- Release processed chunks from memory after use

**Real-time Generation Cache (Temporary Experiments):**
- Keep generated disruptions in memory immediately after creation
- Do NOT remove from memory immediately after use
- Only remove from memory when next disruption batch needs to be loaded
- Prevents redundant file I/O for recently generated files
- Maintain cache of last-used 10 chunks per task (approximately 1000 disruptions per task)
- Cache eviction policy: FIFO (First In, First Out)
- Log cache hits/misses for optimization analysis

**Pre-existing Disruption Loading (Preset Experiments):**
- Load disruptions lazily in 10-chunk batches (100 files per chunk)
- Load next chunk only when current chunk processing reaches 80% completion
- Release previous chunks from memory when new chunks load
- Maintain rolling window of 2 active chunks per thread (current + pre-loaded next)
- Use memory-mapped files for large disruption sets when available
- Implement LRU cache for frequently accessed disruptions

#### Disruption Metadata
- Return disruption metadata for frontend display without loading full data:
  - Total file count
  - Generation status (not_started/in_progress/completed)
  - Loaded chunk count and range
  - Cache statistics (hit rate, memory usage)
  - Estimated completion time
- Provide metadata via separate API endpoint
- Update metadata in real-time via WebSocket
- Enable frontend to show progress bars and status indicators

## Implementation Requirements

### Data Handling
- Python backend performs ALL parsing of CPP API results
- Python backend performs ALL calculations and aggregations
- Python backend generates display-ready data structures
- Python backend writes `progress.json` with all thread status and complete metrics
- Python backend saves each CPP API result as individual JSON file
- Frontend receives pre-formatted display data (no processing needed)
- Frontend reads `progress.json` for real-time updates via WebSocket
- Ensure accuracy in parsing, calculations, and display
- Maintain exact metric format as shown in UI reference image
- Validate all metrics before writing to progress.json
- WebSocket server must handle multiple concurrent connections per experiment
- WebSocket must reconnect gracefully on connection loss
- WebSocket must validate client authorization before sending sensitive data

### Backend WebSocket Implementation
- Use Flask-SocketIO for WebSocket support
- Namespace: `/api/experiment/[id]/status`
- Event types:
  - `connect`: Client connects, receive initial state
  - `progress_update`: Broadcast progress change to all clients
  - `disconnect`: Client disconnects
  - `error`: Send error message to client
- Store WebSocket session state per client
- Validate demo_id in connection request
- Broadcast state changes to all connected clients
- Handle reconnection by replaying last known state

### Frontend WebSocket Implementation
- Connect to WebSocket on experiment start
- Establish event listeners for `progress_update` and `error` events
- Update UI components on each message
- Handle disconnection with reconnect attempts (max 5 retries, exponential backoff)
- Display connection status indicator
- Send keepalive pings every 30 seconds
- Display timestamp of last update received

### Metric Categories Per Thread
Each thread in `progress.json` must track:

1. **Thread Identification:**
   - Thread ID (unique identifier)
   - Trial number (X/Y format, e.g., "1/3")
   - Batch number if applicable (X/Y format)
   - Route progress (X/Y format, e.g., "3/25")
   - Algorithm name (e.g., "DHL", "Dijkstra")
   - Thread status (running/paused/completed/error)

2. **Last Result Metrics:**
   - Route string (Origin → Destination)
   - Algorithm used
   - Query Time (ms, with precision)
   - Distance (km, rounded to 2 decimals)
   - Baseline ETA (formatted time)
   - Actual ETA (formatted time)
   - Time Impact (seconds, can be negative)
   - Label Size (integer count)

3. **Update Phase Metrics:**
   - Update phase status/type (immediate_update/lazy/etc.)
   - Lazy Update Time (ms, 0.000 format)
   - Update Strategy (string description)
   - Max Label Size (integer)
   - Min Label Size (integer)
   - Nodes Repaired (HC2L only, N/A for others)
   - Dirty Nodes (HC2L only, N/A for others)
   - Impact Score (float or N/A)

4. **Query Phase Metrics:**
   - Algorithm identifier (string)
   - Avg Query Time (ms, with precision)
   - Std Dev (float or N/A)
   - Min Query Time (ms)
   - Max Query Time (ms or N/A if single query)
   - P95 Latency (ms or N/A)
   - Queries Count (integer)

5. **Results History:**
   - Total count (integer)
   - Highlights array (limited to 10 most recent/significant entries)
   - Each highlight contains timestamp and key metrics

6. **Thread Progress:**
   - Current route index
   - Total routes for this thread
   - Percentage complete
   - Estimated time remaining
   - Routes per minute (throughput)

### Error Handling
- All backend functions must have comprehensive error handling
- Errors logged with context (thread ID, route, algorithm)
- WebSocket errors sent to client with human-readable messages
- Graceful degradation: partial results saved on thread failure
- Automatic thread restart on transient failures (up to 3 retries)
- Fatal errors trigger experiment pause and notification
- Exception logging includes stack trace for debugging

### Logging
- Add detailed logging for all multi-threaded execution
- Log thread start/stop events with timestamps
- Log disruption generation progress (chunks processed, cache hits)
- Log WebSocket connection/disconnection events
- Log performance metrics (throughput, latency per thread)
- Use consistent log format with component prefixes
- Archive logs per experiment run for analysis

## Validation Checklist
- [ ] ExperimentPreset.json creation and validation working
- [ ] Temporary experiment config generation functional
- [ ] Preset disruptions load with lazy-loading chunks
- [ ] Temporary disruptions generate with 10-chunk batches
- [ ] All parsing is accurate and correct (verify against known test cases)
- [ ] All calculations are proper and verified (unit tests for aggregations)
- [ ] All displayed information is correct (matches CPP API output)
- [ ] Multi-threading implementation works correctly (tested with 3 and 9 threads)
- [ ] `progress.json` tracks ALL threads with complete metrics
- [ ] Each thread shows all required metrics (Last Result, Update Phase, Query Phase)
- [ ] WebSocket real-time updates functioning (tested with multiple clients)
- [ ] Cache management (create/clear) operational (tested all scenarios)
- [ ] Lazy disruption generation working (10 chunks per task verified)
- [ ] Real-time generation memory caching functional (cache hit rate logged)
- [ ] Pre-existing disruption lazy loading working (memory usage verified)
- [ ] Disruption metadata returned properly (all fields present)
- [ ] Backend API routes all functional (API tests pass)
- [ ] Frontend display-only implementation complete (no computation in JS)
- [ ] Per-thread metric display matches UI reference image exactly
- [ ] Multi-thread color coding working correctly on map
- [ ] Thread selection/highlighting functional
- [ ] Auto-detection of threading needs working correctly
- [ ] Resource monitoring and dynamic thread adjustment functional
- [ ] WebSocket reconnection working after connection loss
- [ ] Temporary experiment cleanup functioning (all files removed)
- [ ] Preset experiment persistence verified (survives restarts)

## Development Notes (CRITICAL - READ CAREFULLY)
- **Work continuously until complete** - focus on experiment runner only
- **Do NOT create markdown files or summary documents during work** - just code
- **Study all necessary components thoroughly** before implementing
- **Test extensively** before considering complete
- **Reference UI reference image** for exact metric display requirements
- **Priority order:** Correctness > Performance > Code cleanliness
- **When in doubt about a metric:** Check CPP API output format first
- **Error handling:** All backend functions must have comprehensive error handling
- **Logging:** Add detailed logging for debugging multi-threaded execution
- **Experiment-only focus:** REMOVE all demo-related code, implement experiment runner exclusively
- **WebSocket critical:** Ensure robust WebSocket implementation with connection recovery
- **File structure required:** Use exact paths specified above (preset vs temporary separation)