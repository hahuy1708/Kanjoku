# Kanjoku

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![Type](https://img.shields.io/badge/focus-JLPT%20N1--N5-orange.svg)

Kanjoku is a lightweight project designed to gene is a lightweight project designed torate JLP-style quizzes from JLPT vocabulary JSON files.

## Folder structure

```
data/
	vocab_json/     # Input JLPT vocab JSON files (n1.json..n5.json)
	output/         # Generated quiz JSON files
src/
	constants.py
	reading/
		quiz.py         # Reading quiz runner
		distractors.py  # High-quality JMdict-based reading distractors
		utils.py        # Mora tools, okurigana, phonetic scoring
	context/
		quiz.py         # Context module scaffold
	usage/
		pipeline.py     # Usage quiz generation pipeline (LLM)
		prompts.py      # Prompt templates
		llm_client.py   # Gemini client
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

### Generate Reading Quiz (local, no LLM)

```bash
python main.py --level 2 --mode reading
```

### Generate Usage Quiz (LLM)

```bash
python main.py --level 2 --mode usage --batch 4
```

### Compatibility alias

`--mode ai` is kept as an alias of `--mode usage`.

```bash
python main.py --level 2 --mode ai --batch 4
```

### Generate all currently implemented flows

```bash
python main.py --level 2 --mode all
```

### Optional flags

```bash
python main.py --level 2 --mode reading --limit 40
python main.py --level 2 --mode usage --limit 20 --batch 4
```

## Question types

- **Reading**: Kanji -> Reading (hiragana), generated locally using JMdict constraints.
- **Context**: Module scaffold is present but generation flow is not implemented yet.
- **Usage**: 4 Japanese sentences; choose the sentence that uses the target word correctly.

## Notes

- Reading is fully local and does not require API calls.
- Usage requires a valid `GEMINI_API_KEY`.
- Output files are written to `data/output/n{level}/`.


## Data sources & Credits
- This project was inspired by [sofyc/ConQuer](https://github.com/sofyc/ConQuer) to create quizzes from structured data using LLMs.
- While ConQuer provides a broader structure, this project adapts the idea to focus specifically on JLPT vocabulary quizzes, utilizing strict JSON prompts and diverse question types for better quiz quality.  
- The vocabulary JSON files used in this project were sourced from [wkei/jlpt-vocab-api](https://github.com/wkei/jlpt-vocab-api).

