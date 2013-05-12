#!/bin/bash -ex
#
# Test command-line usage.

echo 'This is okay.' | python -m language_tool -
! echo 'This is noot okay.' | python -m language_tool -
