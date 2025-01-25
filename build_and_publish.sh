rm -rf build/ dist/ *.egg-info/
python -m pip install --upgrade pip setuptools wheel build
python -m build
twine check dist/*
twine upload dist/* --verbose