#!/bin/bash -ex
#
# Test command-line usage.

trap "echo -e '\x1b[01;31mFailed\x1b[0m'" ERR

#export ARGS="--remote-host localhost --remote-port 8080"
export ARGS=""

echo 'This is okay.' | language-check ${ARGS} -
! echo 'This is noot okay.' | language-check ${ARGS} -

echo 'This is okay.' | python -m language_check ${ARGS} -
! echo 'This is noot okay.' | python -m language_check ${ARGS} -

echo 'These are “smart” quotes.' | python -m language_check ${ARGS} -
! echo 'These are "dumb" quotes.' | python -m language_check ${ARGS} -
! echo 'These are "dumb" quotes.' | python -m language_check ${ARGS} --enabled-only \
    --enable=EN_QUOTES -
echo 'These are "dumb" quotes.' | python -m language_check ${ARGS} --enabled-only \
    --enable=EN_UNPAIRED_BRACKETS -

echo '# These are "dumb".' | python -m language_check ${ARGS} --ignore-lines='^#' -

echo -e '\x1b[01;32mOkay\x1b[0m'
