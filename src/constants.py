# src/constants.py
import os

# Base data directories
VOCAB_DIR = os.path.join("data", "vocab_json")
OUTPUT_DIR = os.path.join("data", "output")
TATOEBA_DB  = os.path.join("data", "tatoeba", "tatoeba.db")

def vocab_path(level):
    return os.path.join(VOCAB_DIR, f"n{level}.json")

def output_dir_for(level):
    return os.path.join(OUTPUT_DIR, f"n{level}")
