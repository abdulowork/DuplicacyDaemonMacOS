venv_python = venv/bin/python

.PHONY: *

install_python:
	pyenv install -s

create_venv: install_python
	pyenv exec python -m venv venv

install_requirements: create_venv
	$(venv_python) -m pip install --upgrade pip
	$(venv_python) -m pip install -r requirements/dev.txt

mypy: install_requirements
	$(venv_python) -m mypy --strict --exclude bin .

black: install_requirements
	$(venv_python) -m black --extend-exclude bin .

quality: black mypy
