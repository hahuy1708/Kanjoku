# Kanjoku

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![Type](https://img.shields.io/badge/focus-JLPT%20N1--N5-orange.svg)

Kanjoku is a lightweight project designed to generate JLPT-style quizzes from JLPT vocabulary JSON files.

## Folder structure

```
data/
	vocab_json/     # Input JLPT vocab JSON files (n1.json..n5.json)
	output/         # Generated quiz JSON files
src/
	distractors.py  # Reading + semantic distractors
	prompts.py      # Strict JSON prompts for LLM
	llm_client.py   # OpenAI / Gemini client
	pipeline.py     # Main pipeline: JSON -> LLM -> JSON
    quiz_reading.py # Local reading quiz generator (long vowels, sokuon, dakuon)
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

## Usage

### Create your `.env` file with your Gemini API key

```bash
GEMINI_API_KEY=your-gemini-key
```

### Generate Reading Quizzes

```bash
python src/quiz_reading.py
```

### Generate Context & Usage Quizzes (LLM Required)

```bash
python src/pipeline.py
```

## Question types

- **Reading**: Kanji -> Reading (hiragana). Distractors are generated locally (long vowels / sokuon / dakuon).
- **Context**: One Japanese sentence with a blank (`____`). Pick the correct word.
- **Usage**: 4 Japanese sentences. Choose the one that uses the target word correctly.

## 


## Data sources & Credits
- This project was inspired by [sofyc/ConQuer](https://github.com/sofyc/ConQuer) to create quizzes from structured data using LLMs.
- While ConQuer provides a broader structure, this project adapts the idea to focus specifically on JLPT vocabulary quizzes, utilizing strict JSON prompts and diverse question types for better quiz quality.  
- The vocabulary JSON files used in this project were sourced from [wkei/jlpt-vocab-api](https://github.com/wkei/jlpt-vocab-api).

