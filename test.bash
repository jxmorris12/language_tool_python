#!/bin/bash
#
# Test command-line usage.

set -ex

trap "echo -e '\x1b[01;31mFailed\x1b[0m'" ERR

echo 'This is okay.' | language_tool_python -
! echo 'This is noot okay.' | language_tool_python -

echo 'This is okay.' | python -m language_tool_python -
! echo 'This is noot okay.' | python -m language_tool_python -

echo 'These are “smart” quotes.' | python -m language_tool_python -
! echo 'These are "dumb" quotes.' | python -m language_tool_python -
! echo 'These are "dumb" quotes.' | python -m language_tool_python --enabled-only \
    --enable=EN_QUOTES -
echo 'These are "dumb" quotes.' | python -m language_tool_python --enabled-only \
    --enable=EN_UNPAIRED_BRACKETS -

echo '# These are "dumb".' | python -m language_tool_python --ignore-lines='^#' -

echo -e '\x1b[01;32mOkay\x1b[0m'
