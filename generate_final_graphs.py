# =================================================
#
# FINAL UNIFIED THESIS ANALYSIS & VISUALIZATION SCRIPT
#
# This script combines the robust data loading from the original script
# with the improved, chronologically accurate visualization techniques.
# It runs a single, definitive analysis on the complete data snapshot.
#
# =================================================

import os
import json
import pandas as pd
from datetime import datetime
import networkx as nx
import plotly.express as px
import plotly.graph_objects as go
import leidenalg as la
import igraph as ig
from scipy.spatial import ConvexHull
import numpy as np
import re

# ---  MASTER CONFIGURATION  ---
VAULT_PATH = 'INSERT_YOUR_ABSOLUTE_VAULT_PATH_HERE'
JSON_FILENAME = 'metadata.json'
LEIDEN_RESOLUTION = 1.0 
TOP_N_COMMUNITIES = 10
OUTPUT_DIR = "Final_Graphs_Corrected"

# --- 0. SETUP ---
print("--- 0. Setting up Environment ---")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"Created output directory: '{OUTPUT_DIR}'")

# --- 1. Load, Enrich, and CLEAN Data (Robust Method) ---
print("\n--- 1. Loading, Enriching, and Cleaning Data ---")
JSON_FILENAME = os.path.join('.obsidian', 'plugins', 'metadata-extractor', 'metadata.json')
full_json_path = os.path.join(VAULT_PATH, JSON_FILENAME)
try:
    with open(full_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"\nFATAL ERROR: Could not find '{JSON_FILENAME}'. Please check VAULT_PATH."); exit()

enriched_data = []
for note in data:
    try:
        full_note_path = os.path.join(VAULT_PATH, note['relativePath'])
        if not os.path.exists(full_note_path):
            base_dir_for_fix = '/Users/cousincrock/Documents/Cousin Crock'
            potential_path = os.path.join(base_dir_for_fix, note['relativePath'])
            if os.path.exists(potential_path):
                full_note_path = potential_path
            else:
                continue
        
        file_stats = os.stat(full_note_path)
        note['creation_date'] = datetime.fromtimestamp(getattr(file_stats, 'st_birthtime', file_stats.st_ctime))
        note['modification_date'] = datetime.fromtimestamp(file_stats.st_mtime)
        enriched_data.append(note)
    except (FileNotFoundError, TypeError, KeyError):
        note.update({'creation_date': pd.NaT, 'modification_date': pd.NaT})

df = pd.DataFrame(enriched_data)
df.dropna(subset=['creation_date', 'modification_date', 'relativePath', 'fileName'], inplace=True)
df['links'] = df['links'].apply(lambda x: [link['link'] for link in x if 'link' in link] if isinstance(x, list) else [])
df = df.drop_duplicates(subset='fileName', keep='first').reset_index(drop=True)
print(f"Loaded and cleaned data for {len(df)} unique notes.")

# --- 2. Build Graph ---
print("\n--- 2. Building Full Weighted Knowledge Graph ---")
G_full = nx.Graph()
all_nodes_in_df = set(df['fileName'])
DAILY_NOTE_PATTERN = r'^\d{4}-\d{2}-\d{2}'
for _, row in df.iterrows():
    source_node = row['fileName']
    G_full.add_node(source_node)
    is_daily_note = bool(re.match(DAILY_NOTE_PATTERN, source_node))
    link_weight = 0.1 if is_daily_note else 1.0
    for target_node in row['links']:
        if target_node in all_nodes_in_df:
            G_full.add_edge(source_node, target_node, weight=link_weight)
print(f"Graph built with {G_full.number_of_nodes()} nodes and {G_full.number_of_edges()} edges.")

# --- 3. Run Leiden and Auto-Label ---
print("\n--- 3. Running Leiden and Auto-Labeling Communities ---")
node_to_id = {node: i for i, node in enumerate(G_full.nodes())}
G_ig_full = ig.Graph(n=len(G_full.nodes()), edges=[(node_to_id[u], node_to_id[v]) for u, v in G_full.edges()], directed=False)
G_ig_full.vs['name'] = list(node_to_id.keys())
G_ig_full.es['weight'] = [float(d.get('weight', 1.0)) for u, v, d in G_full.edges(data=True)]
partition = la.find_partition(G_ig_full, la.RBConfigurationVertexPartition, weights='weight', resolution_parameter=LEIDEN_RESOLUTION, seed=42)
community_map = {G_ig_full.vs[i]['name']: membership for i, membership in enumerate(partition.membership)}
df['community_id'] = df['fileName'].map(community_map).fillna(-1).astype(int)
community_labels = {i: max(G_full.subgraph(G_ig_full.vs[nodes]['name']), key=nx.pagerank(G_full.subgraph(G_ig_full.vs[nodes]['name']), weight='weight').get) for i, nodes in enumerate(partition) if nodes}
df['community_label'] = df['community_id'].map(community_labels).fillna("Unclustered")
df['community_short_label'] = df['community_label'].apply(lambda x: (x[:35] + '...') if isinstance(x, str) and len(x) > 38 else x)

# --- 4. Calculate Final Metrics ---
print("\n--- 4. Calculating Final Node Metrics ---")
df['link_count'] = df['fileName'].apply(lambda n: G_full.degree(n) if n in G_full else 0)
df['disruption_score'] = df.apply(lambda row: sum(1 for n in G_full.neighbors(row['fileName']) if community_map.get(n, -1) != row['community_id']) / row['link_count'] if row['link_count'] > 0 else 0, axis=1)
df['node_type'] = df['fileName'].apply(lambda name: 'Rhizome' if bool(re.match(DAILY_NOTE_PATTERN, name)) else 'Artefact')

# --- 5. Prepare Final DataFrame for Plotting ---
print("\n--- 5. Preparing Data for Visualization Suite ---")
top_communities_ids = df[df['community_id'] != -1]['community_id'].value_counts().nlargest(TOP_N_COMMUNITIES).index
plot_df = df[df['community_id'].isin(top_communities_ids)].copy()

# --- 6. Generate Visualization Suite ---
print("\n--- 6. Generating Visualizations ---")
colors = px.colors.qualitative.Plotly

# VISUALISATION 1: Chronological Timeline
try:
    print("Generating 1: Chronological Timeline...")
    community_first_date = plot_df.groupby('community_short_label')['creation_date'].min().sort_values()
    plot_df['community_short_label_sorted'] = pd.Categorical(plot_df['community_short_label'], categories=community_first_date.index, ordered=True)
    fig_timeline = px.scatter(
        plot_df.sort_values(['community_short_label_sorted', 'creation_date']),
        x='creation_date', y='community_short_label_sorted', color='community_short_label',
        title='Community Activity Timeline (Chronological)', hover_name='fileName',
        hover_data={'community_label': True, 'link_count':True, 'modification_date': True},
        labels={'community_short_label_sorted': 'Emergent Theme', 'creation_date': 'Creation Date'},
        size='link_count', size_max=20)
    fig_timeline.update_layout(height=900, template='plotly_dark', showlegend=True, legend_title_text='Top Themes')
    fig_timeline.update_xaxes(dtick="M1", tickformat="%b\n%Y")
    fig_timeline.write_html(os.path.join(OUTPUT_DIR, '1_chronological_timeline.html'))
    print(f"  -> Success! Saved to '{OUTPUT_DIR}/1_chronological_timeline.html")
except Exception as e: print(f"  -> ERROR generating timeline: {e}")

# VISUALISATION 2: Disruption Bubble Chart
try:
    print("Generating 2: Disruption Bubble Chart...")
    bubble_df = plot_df.copy()
    fig_bubble = px.scatter(bubble_df, x="disruption_score", y="link_count", size="link_count", color="community_short_label", hover_name="fileName", hover_data={'community_label': True}, log_y=True, title="Emergence Map: Disruption vs. Connectivity", labels={"disruption_score": "Disruption Score (1=Bridging)", "link_count": "Connectivity (Log Scale)", "community_short_label": "Emergent Theme"}, size_max=50)
    fig_bubble.update_layout(height=800, template='plotly_dark', legend_title_text='Top Themes')
    fig_bubble.write_html(os.path.join(OUTPUT_DIR, '2_disruption_bubble_chart.html'))
    print(f"  -> Success! Saved to '{OUTPUT_DIR}/2_disruption_bubble_chart.html")
except Exception as e: print(f"  -> ERROR generating bubble chart: {e}")

# VISUALISATION 3: 2D Spatial Map with Auras
try:
    print("Generating 3: 2D Spatial Map with Auras...")
    core_G_2d = G_full.subgraph(plot_df['fileName']).copy()
    pos_2d = nx.spring_layout(core_G_2d, k=0.35, iterations=80, seed=42)
    fig_2d = go.Figure()
    for i, community_id in enumerate(top_communities_ids):
        community_nodes_df = plot_df[plot_df['community_id'] == community_id]
        if community_nodes_df.empty: continue
        short_label = community_nodes_df['community_short_label'].iloc[0]
        community_pos = np.array([pos_2d[node] for node in community_nodes_df['fileName'] if node in pos_2d])
        if len(community_pos) > 2:
            try:
                hull = ConvexHull(community_pos)
                x_h = np.append(community_pos[hull.vertices,0], community_pos[hull.vertices,0][0]); y_h = np.append(community_pos[hull.vertices,1], community_pos[hull.vertices,1][0])
                fig_2d.add_trace(go.Scatter(x=x_h, y=y_h, fill="toself", fillcolor=colors[i % len(colors)], line_color=colors[i % len(colors)], opacity=0.15, hoverinfo='none', mode='lines', name=short_label, legendgroup=short_label))
            except: pass
        fig_2d.add_trace(go.Scatter(x=[pos_2d[n][0] for n in community_nodes_df['fileName'] if n in pos_2d], y=[pos_2d[n][1] for n in community_nodes_df['fileName'] if n in pos_2d], mode='markers', hoverinfo='text', text=community_nodes_df['fileName'], name=short_label, legendgroup=short_label, showlegend=False, marker=dict(color=colors[i % len(colors)], size=5)))
    fig_2d.update_layout(title='Emergent Community Network Map (2D)', height=1000, template='plotly_dark', legend_title_text='Top Themes')
    fig_2d.write_html(os.path.join(OUTPUT_DIR, '3_2d_spatial_map.html'))
    print(f"  -> Success! Saved to '{OUTPUT_DIR}/3_2d_spatial_map.html")
except Exception as e: print(f"  -> ERROR generating 2D map: {e}")


# VISUALISATION 4: The Rhizome & Constellations Map (Corrected Proportional Layout)
try:
    print("Generating 4: Rhizome & Constellations Map...")
    core_G_rhizome = G_full.subgraph(plot_df['fileName']).copy()
    pos_rhizome = {}
    rhizome_nodes_df = plot_df[plot_df['node_type'] == 'Rhizome'].sort_values('creation_date')
    artefact_nodes = [n for n in core_G_rhizome.nodes() if n not in rhizome_nodes_df['fileName'].tolist()]
    
    gap_start_date = datetime(2023, 10, 1)
    gap_end_date = datetime(2024, 2, 1)
    
    pre_gap_nodes = rhizome_nodes_df[rhizome_nodes_df['creation_date'] < gap_start_date]['fileName'].tolist()
    post_gap_nodes = rhizome_nodes_df[rhizome_nodes_df['creation_date'] >= gap_end_date]['fileName'].tolist()

    total_nodes = len(pre_gap_nodes) + len(post_gap_nodes)
    if total_nodes > 0:
        pre_ratio = len(pre_gap_nodes) / total_nodes
        post_ratio = len(post_gap_nodes) / total_nodes
        total_width = 5.0; gap_width = 0.5
        pre_width = (total_width - gap_width) * pre_ratio
        post_width = (total_width - gap_width) * post_ratio
        
        pre_gap_x = np.linspace(-total_width/2, -total_width/2 + pre_width, len(pre_gap_nodes)) if pre_gap_nodes else []
        post_gap_x = np.linspace(total_width/2 - post_width, total_width/2, len(post_gap_nodes)) if post_gap_nodes else []

        for i, node in enumerate(pre_gap_nodes): pos_rhizome[node] = (pre_gap_x[i], -2.5)
        for i, node in enumerate(post_gap_nodes): pos_rhizome[node] = (post_gap_x[i], -2.5)

    if artefact_nodes:
        artefact_subgraph = core_G_rhizome.subgraph(artefact_nodes)
        if artefact_subgraph.number_of_nodes() > 0:
             pos_rhizome.update(nx.spring_layout(artefact_subgraph, k=0.9, iterations=80, seed=42, center=(0,0)))

    fig_rhizome = go.Figure()
    
    for i, comm_id in enumerate(top_communities_ids):
        comm_nodes = plot_df[plot_df['community_id'] == comm_id]['fileName'].tolist()
        short_label = plot_df[plot_df['community_id'] == comm_id]['community_short_label'].iloc[0]
        edge_x, edge_y = [], []
        for u, v in core_G_rhizome.edges(comm_nodes):
            if u in pos_rhizome and v in pos_rhizome:
                x0,y0=pos_rhizome[u]; x1,y1=pos_rhizome[v]
                edge_x.extend([x0,x1,None]); edge_y.extend([y0,y1,None])
        fig_rhizome.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines', line=dict(width=0.4, color=colors[i % len(colors)]), hoverinfo='none', name=short_label, legendgroup=short_label))

    rhizome_plot_nodes = pre_gap_nodes + post_gap_nodes
    fig_rhizome.add_trace(go.Scatter(x=[pos_rhizome[n][0] for n in rhizome_plot_nodes if n in pos_rhizome], y=[pos_rhizome[n][1] for n in pos_rhizome], mode='markers', name='Rhizome (Process)', text=rhizome_plot_nodes, hoverinfo='text', marker=dict(color='grey', size=4)))
    
    for i, comm_id in enumerate(top_communities_ids):
        comm_nodes_df = plot_df[(plot_df['community_id'] == comm_id) & (plot_df['node_type'] == 'Artefact')]
        node_x = [pos_rhizome[n][0] for n in comm_nodes_df['fileName'] if n in pos_rhizome]
        node_y = [pos_rhizome[n][1] for n in comm_nodes_df['fileName'] if n in pos_rhizome]
        fig_rhizome.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers', name=short_label, text=comm_nodes_df['fileName'], hoverinfo='text', legendgroup=short_label, showlegend=False, marker=dict(color=colors[i % len(colors)], size=comm_nodes_df['link_count'].apply(lambda x: 4 + x**0.6))))
    
    fig_rhizome.update_layout(title='Map of Rhizomatic Praxis (Proportional Chronological Layout)', template='plotly_dark', height=900, legend_title_text='Top Themes')
    fig_rhizome.write_html(os.path.join(OUTPUT_DIR, '4_rhizome_praxis_map.html'))
    print(f"  -> Success! Saved to '{OUTPUT_DIR}/4_rhizome_praxis_map.html")
except Exception as e: print(f"  -> ERROR generating rhizome map: {e}")

# VISUALISATION 5: 3D Spatial Network Graph
try:
    print("Generating 5: 3D Spatial Community Network Map...")
    core_G_3d = G_full.subgraph(plot_df['fileName']).copy()
    pos_3d = nx.spring_layout(core_G_3d, dim=3, k=0.5, iterations=50, seed=42)
    fig_3d = go.Figure()
    edge_x, edge_y, edge_z = [],[],[]
    for u,v in core_G_3d.edges():
        if u in pos_3d and v in pos_3d: x0,y0,z0=pos_3d[u]; x1,y1,z1=pos_3d[v]; edge_x.extend([x0,x1,None]); edge_y.extend([y0,y1,None]); edge_z.extend([z0,z1,None])
    fig_3d.add_trace(go.Scatter3d(x=edge_x, y=edge_y, z=edge_z, mode='lines', line=dict(color='#888', width=1), hoverinfo='none', name='edges'))
    for i, community_id in enumerate(top_communities_ids):
        community_nodes_df = plot_df[plot_df['community_id'] == community_id]
        if community_nodes_df.empty: continue
        short_label = community_nodes_df['community_short_label'].iloc[0]
        node_x, node_y, node_z, node_text, node_size = [],[],[],[],[]
        for _, row in community_nodes_df.iterrows():
            if row['fileName'] in pos_3d:
                x,y,z=pos_3d[row['fileName']]; node_x.append(x); node_y.append(y); node_z.append(z)
                node_text.append(f"{row['fileName']}<br>Links: {row['link_count']}")
                node_size.append(4 + row['link_count']**0.5)
        fig_3d.add_trace(go.Scatter3d(x=node_x, y=node_y, z=node_z, mode='markers', hoverinfo='text', text=node_text, name=short_label, marker=dict(color=colors[i % len(colors)], size=node_size, sizemode='diameter')))
    fig_3d.update_layout(title='3D Emergent Community Network', height=900, template='plotly_dark', legend_title_text='Top Themes', scene=dict(zaxis=dict(title='z')))
    # fig_3d.data[0].showlegend = False # Allow toggling edges
    fig_3d.write_html(os.path.join(OUTPUT_DIR, '5_3d_spatial_map.html'))
    print(f"  -> Success! Saved to '{OUTPUT_DIR}/5_3d_spatial_map.html'")
except Exception as e: print(f"  -> ERROR generating 3D map: {e}")

print("\n--- Analysis and Visualization Complete ---")