# cp-gpre
### competitive programming - guide and problem recommendation engine
building one stop solution for competitive programming .

## usage

- data/topics.json -> list of algorithm/topics useful for cp
- core/model/ -> has instructions for local llm
- core/pipeline/localModel.py -> goes through all the topics in topics.json and gives this to local llm and makes db.json with all the content

- core/practice/ProblemList.py -> refreshes `data/problems.json` (Codeforces) and `data/cses_problems.json` (CSES)
- core/practice/scrape_cses.py -> scrape all CSES tasks (`PYTHONPATH=. python core/practice/scrape_cses.py`)
- core/practice/cses_profile.py -> sync solved CSES tasks via login (cached in `data/cses_progress_<user>.json`)

On the Practice page, enter your CSES username and password once to sync progress; only **unsolved** (AC) CSES tasks are recommended afterward. Password is not stored.

- app.py -> runs a flask server app and displays content from db.json

## screenshot

![ Resource Home Page Screenshot](screenshot/resourceHomepage.png)
![ Binary Search Tree Screenshot](screenshot/binarySearchTree.png)

## to-do list


- [ ] for each topic show other articles from web 
- [ ] make db.json better
- [ ] make a rag system
