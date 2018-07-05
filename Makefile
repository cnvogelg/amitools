# Makefile for musashi

DIST_DIR = dist

PYTHON = python
#PYTHON = python-dbg

.PHONY: all clean_gen clean_gen clean_all
.PHONY: do_gen do_build_inplace do_test do_dev do_install

do_build_inplace: do_gen
	$(PYTHON) setup.py build_ext -i

do_test: do_gen
	$(PYTHON) setup.py test

do_install: do_gen
	$(PYTHON) setup.py install

do_dev: do_gen
	$(PYTHON) setup.py develop --user

clean: clean_gen
	$(PYTHON) setup.py clean

clean_all: clean
	rm -rf $(DIST_DIR)

clean_git:
	git clean -fxd

clean_py:
	find . -name *.pyc -exec rm {} \;

sdist:
	$(PYTHON) setup.py sdist --formats=zip

upload: sdist
	twine upload dist/*

docker-build:
	docker build -t amitools-tox .

