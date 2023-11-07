@echo off

echo black:
black --line-length 120 --verbose .
if errorlevel 1 goto Done

echo.
echo flake8:
flake8 tree_inventory tests --count --max-line-length=120 --extend-ignore=E203,E266,E501,W503,F403,E722,F541 --statistics
if errorlevel 1 goto Done

echo.
echo mypy:
mypy tree_inventory/__main__.py
if errorlevel 1 goto Done

echo.
echo pip install -e .:
pip install -e .
if errorlevel 1 goto Done

echo.
echo pytest:
pytest tests/ --durations=0
if errorlevel 1 goto Done

:Done
echo.
