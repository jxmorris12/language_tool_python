check:
	pycodestyle \
		--exclude ./language_tool_python/LanguageTool-* \
		--ignore=E402,W504 \
		./language_tool_python \
		./language_tool_python/ \
		$(wildcard *.py)
	pylint \
		--rcfile=/dev/null \
		--errors-only \
		--disable=import-error \
		--disable=no-member \
		--disable=no-name-in-module \
		--disable=raising-bad-type \
		./language_tool_python \
		$(wildcard ./language_tool_python/*.py) \
		$(wildcard *.py)
	python setup.py --long-description | rstcheck -
