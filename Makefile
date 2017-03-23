check:
	pycodestyle \
		--exclude ./language_check/LanguageTool-* \
		--ignore=E402 \
		./language-check \
		./language_check/ \
		$(wildcard *.py)
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
		--disable=redefined-variable-type \
		--disable=similarities \
		--disable=too-few-public-methods \
		--disable=too-many-branches \
		--disable=too-many-instance-attributes \
		--disable=too-many-locals \
		--disable=too-many-statements \
		--disable=wrong-import-order \
		--disable=wrong-import-position \
		./language-check \
		$(wildcard ./language_check/*.py) \
		$(wildcard *.py)
	python setup.py --long-description | rstcheck -
