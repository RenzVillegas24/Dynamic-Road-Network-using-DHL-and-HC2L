# Disruptions & Incident Mapping — Tasks and Implementation Plan

## Overview
This document describes required changes to support disruptions (incidents + flow) in the Dynamic Road Network project. It covers references, constraints, tasks, implementation notes, and scripts needed to build and test changes.

## References
- LazyHC2L-Developer-Team-Guide.md — insert the "Proposed Dynamic HC2L Algorithm" section after "Data Generation Procedure*"
- Table 7 & 8 — Rule‑Based Incident Mapping (verify mappings)
- qc_edges.csv — priority / highway hierarchy reference
- HERE Traffic API (incidents + flow) [Read this, for reference too]
    - https://www.here.com/docs/bundle/traffic-api-developer-guide-v7/page/topics/concepts/incidents.html
    - https://www.here.com/docs/bundle/traffic-api-developer-guide-v7/page/topics/concepts/flow.html
- All codes inside the workspace /home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/

## High-level Requirements
- Integrate disruptions (incidents and flow) into the algorithm.
- Support mapping modes from HERE Traffic API mapping.
- Allow selection between incident-only, flow-only, or both modes (user-selectable).
- Do geospatial matching between HERE data and the network edges.
- Use tau as described in project documents and apply it to the algorithm.
- Do not modify the initial edge implementation.
- Do not route through closed roads (respect closure flags).
- Consider highway type; primary roads are higher priority according to qc_edges.csv.

## Constraints & Notes
- Keep the initial edge data structure/implementation unchanged.
- When both mapping modes are available, GUI must allow:
    - selecting which mapping source to apply (mapping mode toggles),
    - selecting traffic data mode: incidents-only, flow-only, or both.
- All disruptions must be considered and fed into the C++ algorithm implementation, according to the selected traffic data mode.
- Consider the HERE API values (speed and etc.) for calculating the ETA.
- Use C++ for algorithm changes (modify existing C++ sources and integrate the disruption inputs).
- Implement geospatial matching routines (snap incidents to edges, consider tolerances described in docs).

## Tasks (developer-visible)
1. Documentation
     - Insert "Proposed Dynamic HC2L Algorithm" after "Data Generation Procedure*" in LazyHC2L-Developer-Team-Guide.md.
     - Create a new tasks/plan .md file outlining the work items below and acceptance criteria, including verification for separate incident/flow modes.
2. Data mapping & ingestion
     - Collect/verify mappings from Table 7 & 8 (Rule‑Based Incident Mapping).
     - Implement parser/mapper for HERE incidents + flow.
     - Support ingest modes: incidents-only, flow-only, and both (merged behavior). Ensure consistent semantics for overlapping data (incident overrides flow or configurable precedence).
     - Add tests and example datasets for each ingest mode.
3. Algorithm changes (C++)
     - Integrate disruptions (incidents & flow) into HC2L/DHL algorithm pipeline, respecting the selected traffic data mode.
     - Apply tau logic as specified in project .md files.
     - Implement checks to avoid routing through closed roads.
     - Preserve initial edge implementation; build on top of it.
     - Use existing project codes/functions where applicable (reuse utilities).
4. Geospatial matching
     - Implement snapping/matching of HERE events to network edges.
     - Respect hierarchy and priorities from qc_edges.csv (primary roads higher priority).
     - Ensure matching logic accounts for selected ingest mode (e.g., when flow-only is selected, ignore incident geometries).
5. GUI
     - Add "Traffic Visualization" settings panel.
     - Add toggle: "Show OSM Graph".
     - Add toggle: "Show Nodes".
     - Add toggle: "Show Active Incidents".
     - Add toggle: "Show Traffic Overlay".
     - Add control: "Traffic Data Mode" with options: "Incidents", "Flow", "Both" (user can select only incidents, only flow, or both).
     - If "Show Traffic Overlay" is ON then show the toggle "For Current Route Only".
     - If "Show Traffic Overlay" is ON then show the "Traffic Data Mode" control.
     - Toggles and mode selection must trigger automatic update of visualization and feed the selected mode into the ingestion pipeline.
6. Build & run
     - Add or update build instructions; ensure C++ changes compile and tests run.
     - Provide test cases for closed roads, priority handling, and each traffic data mode (incidents-only, flow-only, both).
7. Deliverables
     - Updated LazyHC2L-Developer-Team-Guide.md
     - New tasks/plan .md
     - Modified C++ sources with disruption handling (respecting selected traffic data mode)
     - GUI changes (settings + toggles + Traffic Data Mode)
     - Test scripts and example datasets for all modes

## Implementation snippets / commands
Conda (developer environment):
```
conda activate /home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/.conda; exec fish
```

Build:
```
/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/build_all.sh
```

## Checklist before merge
- [ ] Table 8 mappings verified and/or HERE mapping integrated
- [ ] Tau logic implemented and documented
- [ ] Closed roads are excluded from routing
- [ ] Initial edge implementation unchanged
- [ ] Geospatial matching tested
- [ ] GUI toggles added and functioning
- [ ] Traffic Data Mode control added and functional (Incidents / Flow / Both)
- [ ] Unit / integration tests added for each ingest mode
- [ ] Documentation updated (LazyHC2L and tasks .md)

## Next steps
- Create the new tasks/plan .md and break down work items into actionable tickets, including one ticket to implement the Traffic Data Mode and its tests.
- Start with ingestion + mapping (support separate modes), then integrate into C++ algorithm, then GUI.
- Run build and tests; iterate on edge cases (closed roads, overlapping disruptions, mode precedence).

Note: Continue with code generation and implementation after agreeing on mapping approach, confirming Table 8 coverage, and finalizing incident/flow precedence rules.

## Notes
- Modify the codes and only codes not the documentation, those are reference only