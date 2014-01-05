#!/bin/bash -ex
#
# Test command-line usage.

echo 'This is okay.' | language-check -
! echo 'This is noot okay.' | language-check -

echo 'This is okay.' | python -m language_check -
! echo 'This is noot okay.' | python -m language_check -
