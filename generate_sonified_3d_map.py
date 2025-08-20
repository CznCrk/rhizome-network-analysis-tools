# =================================================
#
# SONIFIED 3D SPATIAL MAP GENERATION SCRIPT
#
# This script generates a single, portable, interactive 3D network graph
# with an embedded audio engine.
#
# V8 - Definitive Polish:
# - Implements a robust, asynchronous audio start-up sequence.
# - Adds a "START AUDIO" button that fades out and starts all chords.
# - Changes node timbre to a 'triangle' wave for a softer, more musical tone.
# - Further reduces node ping volume for a better mix.
# - Transposes the core scale up by one octave for audibility.
#
# =================================================

import os
import json
import pandas as pd
from datetime import datetime
import networkx as nx
import plotly.graph_objects as go
import leidenalg as la
import igraph as ig
import re
import plotly.express as px

# --- MASTER CONFIGURATION ---
VAULT_PATH = 'INSERT_YOUR_ABSOLUTE_VAULT_PATH_HERE'
JSON_FILENAME = 'metadata.json'
LEIDEN_RESOLUTION = 1.0
TOP_N_COMMUNITIES = 10

# --- OUTPUT CONFIGURATION ---
OUTPUT_PARENT_DIR = "Sonified_3D_Map"
AUDIO_DIR = os.path.join(OUTPUT_PARENT_DIR, "1_Place_Your_Audio_Files_Here")
HTML_DIR = os.path.join(OUTPUT_PARENT_DIR, "2_Open_This_File_In_Your_Browser")
HTML_FILENAME = os.path.join(HTML_DIR, "sonified_3d_map.html")
README_FILENAME = os.path.join(AUDIO_DIR, "README.txt")

# --- 0. SETUP ---
print("--- 0. Setting up Environment ---")
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)
    print(f"Created audio directory: '{AUDIO_DIR}'")
if not os.path.exists(HTML_DIR):
    os.makedirs(HTML_DIR)
    print(f"Created HTML directory: '{HTML_DIR}'")

# Create README file
readme_content = """
This directory contains the 10 audio files for the sonified map.
The main file to open is in the '2_Open_This_File_In_Your_Browser' directory.

INSTRUCTIONS:
1. Open the 'sonified_3d_map.html' file in a web browser.
2. Click the 'START AUDIO' button to begin the ambient soundscape.
3. Hover over nodes to hear their corresponding pings.
4. Click on community names in the legend to mute and unmute their ambient chords.
"""
with open(README_FILENAME, 'w') as f:
    f.write(readme_content)
print(f"Created README file: '{README_FILENAME}'")


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

# --- 5. Prepare Final DataFrame for Plotting ---
print("\n--- 5. Preparing Data for Visualization ---")
top_communities_ids = df[df['community_id'] != -1]['community_id'].value_counts().nlargest(TOP_N_COMMUNITIES).index
plot_df = df[df['community_id'].isin(top_communities_ids)].copy()
colors = px.colors.qualitative.Plotly

# Calculate max link count for normalization in JS
max_link_count = plot_df['link_count'].max()


# --- 6. Generate Sonified 3D Spatial Map ---
print("\n--- 6. Generating Sonified 3D Map ---")

# Establish the definitive order of communities for audio mapping
top_community_labels_sorted = plot_df.groupby('community_id')['community_short_label'].first().loc[top_communities_ids].tolist()
print("\n--- Community to Audio File Mapping ---")
for i, label in enumerate(top_community_labels_sorted):
    print(f"  {i+1}: '{label}' -> community_{i+1}.mp3")
print("-------------------------------------\n")


try:
    core_G_3d = G_full.subgraph(plot_df['fileName']).copy()
    pos_3d = nx.spring_layout(core_G_3d, dim=3, k=0.5, iterations=50, seed=42)
    
    fig_3d = go.Figure()
    
    # Add Nodes by Community
    for i, community_id in enumerate(top_communities_ids):
        community_nodes_df = plot_df[plot_df['community_id'] == community_id]
        if community_nodes_df.empty: continue
        
        short_label = community_nodes_df['community_short_label'].iloc[0]
        
        node_x, node_y, node_z, node_text, node_size = [],[],[],[],[]
        for _, row in community_nodes_df.iterrows():
            if row['fileName'] in pos_3d:
                x,y,z=pos_3d[row['fileName']]
                node_x.append(x); node_y.append(y); node_z.append(z)
                node_text.append(f"{row['fileName']}<br>Links: {row['link_count']}")
                node_size.append(4 + row['link_count']**0.5)
        
        fig_3d.add_trace(go.Scatter3d(
            x=node_x, y=node_y, z=node_z, 
            mode='markers', 
            hoverinfo='text', 
            text=node_text, 
            name=short_label, 
            legendgroup=short_label,
            marker=dict(color=colors[i % len(colors)], size=node_size, sizemode='diameter')
        ))

    # VISUAL CLEANUP: HIDE AXES AND GRID
    fig_3d.update_layout(
        title='Sonified 3D Emergent Community Network', 
        height=900, 
        template='plotly_dark', 
        legend_title_text='Toggle Communities',
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False)
        )
    )

    # --- HTML & CSS (V19 - VALID DOCTYPE) ---
    html_prefix = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ margin: 0; background-color: #111; color: #fff; font-family: sans-serif; }}
        #plotly-div {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; }}
    </style>
</head>
<body>
    <div id="plotly-div">
"""
    html_suffix = """
    </div>
</body>
</html>
"""

    # --- JAVASCRIPT AUDIO ENGINE INJECTION (V19 - Proven, Simple Logic) ---
    js_engine = f"""
    <script>
        // This script waits for the Plotly graph to be ready, then attaches
        // simple, independent listeners for hover and legend click events.
        
        // --- DATA FROM PYTHON ---
        const communityLabels = {top_community_labels_sorted};
        const maxLinkCount = {max_link_count};
        const USER_SCALE = [98.00, 146.84, 277.18, 440.00, 659.26, 784.00, 1046.50, 1479.98, 1661.22, 1975.54];
        const communityNoteMap = {{
            [communityLabels[0]]: 0, [communityLabels[1]]: 1, [communityLabels[2]]: 2,
            [communityLabels[3]]: 3, [communityLabels[4]]: 4, [communityLabels[5]]: 5,
            [communityLabels[6]]: 6, [communityLabels[7]]: 7, [communityLabels[8]]: 8,
            [communityLabels[9]]: 9, "default": 3
        }};

        // This function sets up all the interactive audio.
        function setupAudioInteraction() {{
            console.log("Plotly graph is ready. Setting up audio interaction...");
            const gd = document.getElementById('plotly-div');

            // --- AUDIO SYSTEM GLOBALS ---
            let pingAudioContext;
            let lastPingTime = 0;
            const audioPlayers = new Array(communityLabels.length).fill(null);

            // --- PING SYSTEM ---
            // This is only called on the first legend click.
            function initPingSystem() {{
                if (pingAudioContext) return;
                console.log("First legend click detected. Initializing ping audio system...");
                pingAudioContext = new (window.AudioContext || window.webkitAudioContext)();
                pingAudioContext.resume().catch(e => console.error("Ping context resume failed:", e));
                console.log("Ping audio context state:", pingAudioContext.state);
            }}

            function playPing(point) {{
                if (!pingAudioContext || pingAudioContext.state !== 'running') return;
                const now = pingAudioContext.currentTime;
                if (now - lastPingTime < 0.05) return;
                lastPingTime = now;

                const communityName = point.fullData.name;
                const linkCount = parseInt(point.text.split('<br>Links: ')[1]) || 0;
                const noteIndex = communityNoteMap[communityName] || communityNoteMap["default"];
                const finalFreq = USER_SCALE[noteIndex];
                
                const logCount = Math.log10(linkCount + 1);
                const logMax = Math.log10(maxLinkCount + 1);
                const normalized = logMax > 0 ? logCount / logMax : 0;
                const attack = 0.01 + (normalized * 0.39);
                const decay = 0.2 + (normalized * 1.8);

                const oscillator = pingAudioContext.createOscillator();
                const filter = pingAudioContext.createBiquadFilter();
                const gainNode = pingAudioContext.createGain();
                oscillator.connect(filter);
                filter.connect(gainNode);
                gainNode.connect(pingAudioContext.destination);

                oscillator.type = 'triangle';
                oscillator.frequency.setValueAtTime(finalFreq, now);
                filter.type = 'lowpass';
                filter.frequency.setValueAtTime(1200, now);
                filter.Q.setValueAtTime(0.5, now);
                gainNode.gain.setValueAtTime(0, now);
                gainNode.gain.linearRampToValueAtTime(0.08, now + attack);
                gainNode.gain.exponentialRampToValueAtTime(0.0001, now + decay);

                oscillator.start(now);
                oscillator.stop(now + decay);
            }}

            // --- ATTACH INTERACTIVE LISTENERS ---
            gd.on('plotly_hover', (data) => {{
                if (pingAudioContext && data.points.length > 0) {{
                    playPing(data.points[0]);
                }}
            }});

            gd.on('plotly_legendclick', event => {{
                // The first legend click unlocks the ping system.
                if (!pingAudioContext) {{
                    initPingSystem();
                }}

                const playerIndex = event.curveNumber;
                if (playerIndex < 0 || playerIndex >= audioPlayers.length) return;

                if (!audioPlayers[playerIndex]) {{
                    console.log(`Creating and playing audio for community ${{playerIndex + 1}}...`);
                    const player = new Audio();
                    player.src = `../1_Place_Your_Audio_Files_Here/community_${{playerIndex + 1}}.mp3`;
                    player.loop = true;
                    player.play().catch(e => console.error(`Player ${{playerIndex + 1}} failed to start:`, e));
                    audioPlayers[playerIndex] = player;
                }} 
                else {{
                    const player = audioPlayers[playerIndex];
                    player.muted = !player.muted;
                    console.log(`Toggling player ${{playerIndex + 1}}. Muted: ${{player.muted}}`);
                }}
            }});
            
            console.log("Audio interaction is now enabled and waiting for the first legend click.");
        }}

        // This is the key: A polling function that waits for Plotly to be ready.
        function initializeWhenReady() {{
            const gd = document.getElementById('plotly-div');
            if (gd && gd.on) {{
                setupAudioInteraction();
            }} else {{
                setTimeout(initializeWhenReady, 50);
            }}
        }}

        // Start the initialization process.
        initializeWhenReady();
    </script>
    """

    # Get the core plot HTML
    plot_html = fig_3d.to_html(full_html=False, include_plotlyjs='cdn')
    
    # Combine all parts
    final_html = html_prefix + plot_html + js_engine + html_suffix

    with open(HTML_FILENAME, 'w', encoding='utf-8') as f:
        f.write(final_html)
        
    print(f"  -> Success! Saved to '{HTML_FILENAME}'")

except Exception as e: 
    print(f"  -> ERROR generating 3D map: {e}")

print("\n--- Sonified 3D Map Generation Complete ---")