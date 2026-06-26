# scripts/check_tatoeba_return.py
from src.context.tatoeba_db import TatoebaDB
from src import constants

db = TatoebaDB(constants.TATOEBA_DB)
result = db.sentences_for_word("機会", limit=3)
print(type(result[0]))   # str or dict?
print(result[0])