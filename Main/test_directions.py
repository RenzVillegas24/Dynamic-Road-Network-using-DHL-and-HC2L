import osmnx as ox
import matplotlib.pyplot as plt

# --- Download the Quezon City drivable network ---
place_name = "Quezon City, Philippines"
G = ox.graph_from_place(place_name, network_type="drive")

# --- Count and classify one-way edges ---
oneway_edges = []
for u, v, data in G.edges(data=True):
    if any(k in data for k in ["oneway", "oneway:forward", "oneway:backward"]):
        oneway_edges.append((u, v, data))

num_oneway = len(oneway_edges)
num_total = len(G.edges)
print(f"Total roads: {num_total}")
print(f"One-way roads: {num_oneway}")

# --- Base map ---
fig, ax = ox.plot_graph(
    G,
    show=False,
    close=False,
    node_size=0,
    edge_color="#cccccc",
    edge_linewidth=0.5,
)

# --- Draw directional arrows with colors based on tagging ---
for u, v, data in oneway_edges:
    if "geometry" in data:
        xs, ys = data["geometry"].xy
    else:
        xs = [G.nodes[u]["x"], G.nodes[v]["x"]]
        ys = [G.nodes[u]["y"], G.nodes[v]["y"]]

    # Determine arrow color by direction tags
    oneway_tag = str(data.get("oneway", "")).lower()
    fwd_tag = str(data.get("oneway:forward", "")).lower()
    bwd_tag = str(data.get("oneway:backward", "")).lower()

    if oneway_tag in ["yes", "true", "1"]:
        color = "red"
    elif oneway_tag in ["-1", "reverse"] or bwd_tag in ["yes", "true", "1"]:
        color = "blue"
    elif fwd_tag in ["yes", "true", "1"]:
        color = "green"
    elif bwd_tag in ["-1", "reverse"]:
        color = "purple"
    else:
        color = None  # Not a one-way tag we care about

    if color:
        ax.annotate(
            "",
            xy=(xs[-1], ys[-1]),
            xytext=(xs[0], ys[0]),
            arrowprops=dict(arrowstyle="->", color=color, lw=1.0, alpha=0.8),
            zorder=3,
        )

# --- Add legend and labels ---
plt.title(f"Quezon City: OSM Oneway Streets\nTotal: {num_total} | Oneway: {num_oneway}", fontsize=10)
plt.xlabel("Longitude")
plt.ylabel("Latitude")

# Legend proxy lines
import matplotlib.lines as mlines
legend_items = [
    mlines.Line2D([], [], color="red", marker=">", linestyle="None", label="oneway=yes"),
    mlines.Line2D([], [], color="blue", marker=">", linestyle="None", label="oneway=-1 / backward"),
    mlines.Line2D([], [], color="green", marker=">", linestyle="None", label="oneway:forward=yes"),
    mlines.Line2D([], [], color="purple", marker=">", linestyle="None", label="oneway:reverse/backward=-1"),
]
plt.legend(handles=legend_items, loc="lower left", fontsize=8)

plt.tight_layout()
plt.show()
