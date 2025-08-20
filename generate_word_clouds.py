# generate_word_clouds.py
# =================================================
#
# A standalone, methodologically sound script to generate TF-IDF word clouds
# for specific, evidence-led periods ("Blooms") within the Obsidian vault.
#
# This script uses the robust data loading logic from the definitive
# graph analysis suite to ensure it works from the single source of truth.
# It is designed to create "Thematic Core Samples" that visualize the
# unique thematic signature of each phase of the research project.
#
# This version is NON-INTERACTIVE and will automatically generate all
# defined bloom snapshots and a full vault summary.
#
# =================================================

import os
import json
import pandas as pd
from datetime import datetime
import re
import markdown
from bs4 import BeautifulSoup
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# ---  MASTER CONFIGURATION  ---
VAULT_PATH = 'INSERT_YOUR_ABSOLUTE_VAULT_PATH_HERE'
JSON_METADATA_PATH = os.path.join(VAULT_PATH, '.obsidian', 'plugins', 'metadata-extractor', 'metadata.json')
OUTPUT_DIR = "Word_Clouds"

# --- NLP Configuration ---
CUSTOM_STOPWORDS = {'obsidian', 'note', 'link', 'page', 'file', 'et', 'al', 'see', 'fig', 'figure', 'completion', 'date', 'task', 'day'}
MIN_WORD_LENGTH = 3

# --- Bloom Date Ranges (Process-Oriented) ---
BLOOM_DATES = {
    "Bloom_1_The_Foundation": ("2022-09-09", "2023-12-31"),
    "Bloom_2_The_Four_Great_Kings": ("2024-01-01", "2024-02-29"),
    "Bloom_3_The_Summer_Riots": ("2024-06-01", "2024-09-30"),
    "Bloom_4_Industry_Drone_Club": ("2024-10-01", "2025-01-31"),
    "Bloom_5_The_Cube_Gig_The_Portrait": ("2025-02-01", "2025-05-31"),
    "Full_Vault": (None, None) # Special case for the entire vault
}

# --- Word Count Configurations ---
WORD_COUNTS_TO_GENERATE = [100, 500]

# --- 0. SETUP ---
def setup_environment():
    """Creates output directory and downloads necessary NLTK models."""
    print("--- 0. Setting up Environment ---")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: '{OUTPUT_DIR}'")
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError: nltk.download('punkt')
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError: nltk.download('stopwords')
    try:
        nltk.data.find('corpora/wordnet')
    except LookupError: nltk.download('wordnet')
    try:
        nltk.data.find('corpora/omw-1.4')
    except LookupError: nltk.download('omw-1.4')
    print("Environment setup complete.")

# --- 1. DATA LOADING AND PREPROCESSING ---
stop_words = set(stopwords.words('english'))
stop_words.update(CUSTOM_STOPWORDS)
lemmatizer = WordNetLemmatizer()

def preprocess_text(markdown_content):
    """Converts markdown to plain text and performs cleaning."""
    try:
        if markdown_content.startswith("---"):
            end_fm = markdown_content.find("---", 3)
            if end_fm != -1: markdown_content = markdown_content[end_fm+3:]
        html = markdown.markdown(markdown_content)
        soup = BeautifulSoup(html, "html.parser")
        for code_block in soup.find_all(["code", "pre"]): code_block.decompose()
        text = soup.get_text(separator=' ')
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[\[([^\]]+?)\]\]', r'\1', text)
        text = re.sub(r'\S*@\S*\s?', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        tokens = word_tokenize(text.lower())
        return " ".join([lemmatizer.lemmatize(w) for w in tokens if w.isalpha() and w not in stop_words and len(w) >= MIN_WORD_LENGTH])
    except Exception:
        return ""

def load_and_process_vault(vault_path, json_path):
    """Loads all notes from the vault using the robust logic from the final analysis suite."""
    print(f"\n--- 1. Loading and Processing Notes from Vault ---")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"\nFATAL ERROR: Could not find metadata file at '{json_path}'."); return None

    enriched_data = []
    print("Reading note contents...")
    for i, note in enumerate(data):
        if not note.get('relativePath'):
            continue
        try:
            full_note_path = os.path.join(vault_path, note['relativePath'])
            
            file_stats = os.stat(full_note_path)
            with open(full_note_path, 'r', encoding='utf-8') as f:
                content = f.read()

            enriched_data.append({
                'fileName': note['fileName'],
                'creation_date': datetime.fromtimestamp(getattr(file_stats, 'st_birthtime', file_stats.st_ctime)),
                'processed_text': preprocess_text(content)
            })
            print(f"\rProcessed {i+1}/{len(data)} notes...", end="")
        except Exception:
            pass
    
    print("\nProcessing complete.")
    df = pd.DataFrame(enriched_data)
    if df.empty:
        print("  -> ERROR: No data loaded. Check VAULT_PATH and JSON file paths.")
        return None
        
    df['creation_date'] = pd.to_datetime(df['creation_date'])
    print(f"Successfully loaded and processed data for {len(df)} unique notes.")
    return df

# --- 2. WORD CLOUD GENERATION ---
def generate_tfidf_wordcloud(full_df, vectorizer, start_date, end_date, case_name, max_words):
    """Filters notes by date range and generates a TF-IDF weighted word cloud."""
    print(f"\n--- Generating Word Cloud for: '{case_name}' ({max_words} words) ---")

    if start_date and end_date:
        mask = (full_df['creation_date'] >= pd.to_datetime(start_date)) & \
               (full_df['creation_date'] <= pd.to_datetime(end_date))
        case_df = full_df.loc[mask]
        print(f"Filtering for date range: {start_date} to {end_date}")
    else:
        case_df = full_df
        print("Using all notes from the entire vault.")

    print(f"Found {len(case_df)} notes for this snapshot.")
    if case_df.empty:
        print("  -> SKIPPING: No notes found in the specified date range.")
        return

    snapshot_text = " ".join(case_df['processed_text'].tolist())
    if not snapshot_text.strip():
        print("  -> SKIPPING: No text content in the filtered notes.")
        return

    case_vector = vectorizer.transform([snapshot_text])
    feature_names = vectorizer.get_feature_names_out()
    scores = case_vector.toarray().flatten()
    word_scores = {word: score for word, score in zip(feature_names, scores) if score > 0}

    if not word_scores:
        print("  -> SKIPPING: No significant words found after TF-IDF.")
        return

    print("Generating word cloud image...")
    wc = WordCloud(
        background_color="black",
        max_words=max_words,
        width=1600,
        height=800,
        colormap='viridis'
    ).generate_from_frequencies(word_scores)

    output_filename = os.path.join(OUTPUT_DIR, f"wordcloud_{case_name}_{max_words}words.png")
    wc.to_file(output_filename)
    print(f"  -> Success! Word cloud saved to '{output_filename}'")

# --- 3. MAIN EXECUTION BLOCK ---
if __name__ == '__main__':
    setup_environment()
    full_vault_df = load_and_process_vault(VAULT_PATH, JSON_METADATA_PATH)

    if full_vault_df is not None:
        print("\n--- Pre-calculating TF-IDF Vectorizer for entire vault ---")
        full_corpus = full_vault_df['processed_text'].tolist()
        tfidf_vectorizer = TfidfVectorizer(smooth_idf=True)
        tfidf_vectorizer.fit(full_corpus)
        print("Vectorizer is ready.")

        for case_name, (start_date, end_date) in BLOOM_DATES.items():
            for word_count in WORD_COUNTS_TO_GENERATE:
                generate_tfidf_wordcloud(
                    full_df=full_vault_df,
                    vectorizer=tfidf_vectorizer,
                    start_date=start_date,
                    end_date=end_date,
                    case_name=case_name,
                    max_words=word_count
                )
        
        print("\n--- All word clouds generated successfully. ---")
    else:
        print("\nCould not load the vault. Please check the paths in the script. Exiting.")