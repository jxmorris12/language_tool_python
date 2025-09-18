check:
	pycodestyle \
		--exclude ./typerfect/LanguageTool-* \
		--ignore=E402,W504 \
		./typerfect \
		./typerfect/ \
		$(wildcard *.py)
	pylint \
		--rcfile=/dev/null \
		--errors-only \
		--disable=import-error \
		--disable=no-member \
		--disable=no-name-in-module \
		--disable=raising-bad-type \
		./typerfect \
		$(wildcard ./typerfect/*.py) \
		$(wildcard *.py)
	python extract_long_description.py | rstcheck -
