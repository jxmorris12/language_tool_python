check:
	pycodestyle \
		--exclude ./language_check/LanguageTool-* \
		--ignore=E402 \
		./language-check \
		./language_check/ \
		$(wildcard *.py)
	pylint \
		--rcfile=/dev/null \
		--errors-only \
		--disable=import-error \
		--disable=no-member \
		--disable=no-name-in-module \
		--disable=raising-bad-type \
		./language-check \
		$(wildcard ./language_check/*.py) \
		$(wildcard *.py)
	python setup.py --long-description | rstcheck -
