#!/bin/bash -ex
#
# Test command-line usage.

echo 'This is okay.' | language-tool -
! echo 'This is noot okay.' | language-tool -

echo 'This is okay.' | python -m language_tool -
! echo 'This is noot okay.' | python -m language_tool -
