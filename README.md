# Data Visualisation Scripts for "Mapping the Performative Rhizome"

This repository contains the Python scripts used for the thesis, "Mapping the Performative Rhizome: An Analysis of Emergence across Multimodal Creative Practices."

These tools read data from an Obsidian.md vault and are provided so that other researchers and artists can apply this data-driven methodology to their own creative practices.

## Scripts Overview

*   **`generate_final_graphs.py`:** The primary analysis script. It generates the five core interactive visualisations used in the thesis's analysis chapter.
*   **`generate_sonified_3d_map.py`:** Generates a unique, playable 3D instrument from your network data.
*   **`generate_word_clouds.py`:** Performs a TF-IDF analysis and generates thematic word clouds for specific periods.

## The Core Methodology

These scripts perform a structural analysis of your creative network. The key algorithms used are:
*   **Leiden Algorithm:** To detect emergent communities of densely connected notes.
*   **PageRank Algorithm:** To identify the most influential or central node within each community, which is then used as that community's thematic label.

## How to Use These Scripts

Follow these steps to analyze your own Obsidian vault.

### Step 1: Download and Install

1.  **Download Code:** Click the green "<> Code" button on this page and select "Download ZIP". Unzip the folder.
2.  **Install Libraries:** Open your computer's command line tool (Terminal on Mac, Command Prompt on Windows), navigate into the downloaded folder, and run:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: The script may need to download NLTK language models on its first run. Please allow it to do so if prompted.*

### Step 2: Set Up Your Python Environment (Recommended)

To keep this project's dependencies separate, it's best to use a virtual environment.

1.  **Create the Environment:** In your command line, run: `python -m venv venv`
2.  **Activate it:**
    *   On **Mac/Linux**: `source venv/bin/activate`
    *   On **Windows**: `venv\Scripts\activate`
    (You should see `(venv)` appear at the start of your command prompt line.)

### Step 3: Configure the VAULT_PATH (Crucial)

You must tell each script where your Obsidian vault is located.

1.  **Find Your Vault Path:** Locate your Obsidian vault folder. Right-click it and use an option like "Copy as Path" to get the full, absolute file path.
2.  **Edit the Scripts:** Open each of the three `.py` files in a text editor. Near the top of each file, find this line:
    ```python
    VAULT_PATH = 'INSERT_YOUR_ABSOLUTE_VAULT_PATH_HERE'
    ```
3.  **Paste Your Path:** Replace the placeholder text with the path you copied. **Ensure the path is inside the quotation marks.**

### Step 4: Run the Analysis

In your command line tool (with the virtual environment still active), run the scripts.

*   **For the main graphs and word clouds:**
    ```bash
    python generate_final_graphs.py
    python generate_word_clouds.py
    ```
    *(These will create the `Final_Graphs_Corrected` and `Word_Clouds` folders.)*

### Step 5: Using the Sonified 3D Map

The sonified map requires one extra step: you must provide the audio files for the ambient community chords.

1.  **Prepare Your Audio:** Create 10 audio files (e.g., ambient chords, drones, textures). They must be in **`.mp3` format**.
2.  **Name Them Correctly:** Name your files exactly as follows:
    `community_1.mp3`, `community_2.mp3`, ..., `community_10.mp3`.
3.  **Run the Script:**
    ```bash
    python generate_sonified_3d_map.py
    ```
4.  **Place the Audio Files:** The script will create a folder structure: `Sonified_3D_Map/1_Place_Your_Audio_Files_Here`. **Copy your 10 `.mp3` files into this folder.**
5.  **Experience the Instrument:** Open the `.html` file located in `Sonified_3D_Map/2_Open_This_File_In_Your_Browser`.

*(When you are finished, you can leave the virtual environment by simply typing `deactivate`.)*

---

### A Note on Reproducibility

The `generate_word_clouds.py` script is an academic artefact. The `BLOOM_DATES` dictionary within it is intentionally hard-coded with the specific date ranges used in the original thesis to ensure the direct reproducibility of its findings. To adapt this script for a different project, a user must modify this dictionary to define their own analytical periods.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.