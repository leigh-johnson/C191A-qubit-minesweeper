# Setup (Python/Stim/Notebooks)

1. Install Python (>=3.11). See [Python Setup and Usage
](https://docs.python.org/3/using/index.html).
1. [Install poetry](https://python-poetry.org/docs/) (dependency and virtual environment management tool for Python)
2. Open a shell prompt and activate the poetry virtual environment:
```bash
$(poetry env activate)
```
3. Confirm you activated the poetry virtual environment by running `which python`. You should see a virtual environment path similar to:
```
$ which python
/Users/leigh/Library/Caches/pypoetry/virtualenvs/c191a-project-IzB3F73c-py3.11/bin/python
```
⚠️ **DO NOT** use your system's python interpreter (e.g. `/usr/local/bin/python` or `/usr/local/bin/python3`).

4. Install python dependencies: 
```bash
$ poetry install
```

# Setup (LaTex)

1. Install LaTex. [MacTex](https://www.tug.org/mactex/mactex-download.html) is the recommended distribution for MacOs. 
2. Install [Vscode](https://code.visualstudio.com/)
3. Install [Latex Workshop Vscode Extension.](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop). Follow the [installation instructions](https://github.com/James-Yu/LaTeX-Workshop/wiki/Install) (setting PATH environment variable) to make sure the extension can find your LaTex installation.
