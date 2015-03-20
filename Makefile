check:
	pep8 --ignore=E402 \
		./language-check ./language_check/ $(wildcard *.py)
	pylint \
		--reports=no \
		--rcfile=/dev/null \
		--disable=attribute-defined-outside-init \
		--disable=bad-continuation \
		--disable=eval-used \
		--disable=import-error \
		--disable=invalid-name \
		--disable=missing-docstring \
		--disable=no-member \
		--disable=no-name-in-module \
		--disable=protected-access \
		--disable=raising-bad-type \
		--disable=similarities \
		--disable=too-few-public-methods \
		--disable=too-many-branches \
		--disable=too-many-locals \
		--disable=too-many-statements \
		./language-check \
		$(wildcard ./language_check/*.py) \
		$(wildcard *.py)
	python setup.py --long-description | rstcheck -
