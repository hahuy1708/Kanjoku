# Kanjoku

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![Type](https://img.shields.io/badge/focus-JLPT%20N1--N5-orange.svg)

Kanjoku is a lightweight project designed to gene is a lightweight project designed torate JLPT-style quizzes from JLPT vocabulary JSON files.

## Folder structure

```
data/
	vocab_json/     # Input JLPT vocab JSON files (n1.json..n5.json)
	output/         # Generated quiz JSON files
	tatoeba/        # Tatoeba sentence data and built database
		jpn_sentences.tsv
		jpn_indices.csv
		tatoeba.db
scripts/
	build_tatoeba_db.py  # Script to build the Tatoeba SQLite database
src/
	constants.py
	reading/
	context/
	usage/
	constants.py
main.py
```

## Install

### Clone the repository
```bash
git clone https://github.com/hahuy1708/Kanjoku.git
cd Kanjoku
```

### Create a virtual environment and install dependencies

```bash
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Create your `.env` file with your Gemini API key

```bash
GEMINI_API_KEY=your-gemini-key
```

## Generate Quiz

### Reading Quiz (Jamdict)

```bash
python main.py --level 2 --mode reading --limit <number_of_questions>
```

### Usage Quiz (LLM)

```bash
python main.py --level 2 --mode usage --limit <number_of_questions> --batch 4
```

### Context Quiz (Tatoeba)

```bash
python main.py --level 2 --mode context --limit <number_of_questions>
```

## Question types

- **Reading**: Kanji -> Reading (hiragana), generated locally using JMdict constraints.
- **Context**: Fill-in-the-blank from real sentences; the target word is removed and becomes the answer. Distractors are generated from similar words in JMdict.
- **Usage**: 4 Japanese sentences; choose the sentence that uses the target word correctly.


## Data sources & Credits
- This project was inspired by [sofyc/ConQuer](https://github.com/sofyc/ConQuer) to create quizzes from structured data using LLMs.
- While ConQuer provides a broader structure, this project adapts the idea to focus specifically on JLPT vocabulary quizzes, utilizing strict JSON prompts and diverse question types for better quiz quality.  
- The vocabulary JSON files used in this project were sourced from [wkei/jlpt-vocab-api](https://github.com/wkei/jlpt-vocab-api).

