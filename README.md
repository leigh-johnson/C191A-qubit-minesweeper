# Setup (Visual Studio Code IDE, also known as VS Code)

1. Install [VS Ccode](https://code.visualstudio.com/)
2. Install [git](https://git-scm.com/install/) command-line tools and clone this repo:
```bash
git clone git@github.com:leigh-johnson/C191A-qubit-minesweeper.git && cd C191A-qubit-minesweeper/
```
# Setup (Python/Stim/Notebooks)

1. Install Python (>=3.11). See [Python Setup and Usage
](https://docs.python.org/3/using/index.html).
3. Install [Jupyter Notebooks extension for VS Code](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter)
4. [Install poetry](https://python-poetry.org/docs/) (dependency and virtual environment management tool for Python)
5. Open a shell prompt and activate the poetry virtual environment:
```bash
$(poetry env activate)
```
5. Confirm you activated the poetry virtual environment by running `which python`. You should see a virtual environment path similar to:
```
$ which python
/Users/leigh/Library/Caches/pypoetry/virtualenvs/c191a-project-IzB3F73c-py3.11/bin/python
```
⚠️ **DO NOT** use your system's Python interpreter (e.g., `/usr/local/bin/python` or `/usr/local/bin/python3`).

6. Install python dependencies: 
```bash
$ poetry install
```
7. Open the getting started notebook: `notebooks/getting_started.ipynb` and make sure the kernel uses the Python interpreter from your virtual environment (NOT your system Python interpreter!)

# Setup (LaTex)

1. Install LaTeX. [MacTex](https://www.tug.org/mactex/mactex-download.html) is the recommended distribution for macOS. 
2. Install [Latex Workshop Vscode Extension.](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop).
Follow the [installation instructions](https://github.com/James-Yu/LaTeX-Workshop/wiki/Install) (setting PATH environment variable) to make sure the extension can find your LaTeX installation.

# Generate example circuits

Correct up to 3 bits between code words:
```
stim --gen repetition_code --task memory --rounds 1000 --distance 3 --after_clifford_depolarization 0.001 --after_reset_flip_probability 0.001 --before_measure_flip_probability 0.002 --before_round_data_depolarization 0.005
```
Correct up to 5 bits between code words:
```
stim --gen repetition_code --task memory --rounds 1000 --distance 5 --after_clifford_depolarization 0.001 --after_reset_flip_probability 0.001 --before_measure_flip_probability 0.002 --before_round_data_depolarization 0.005
```
