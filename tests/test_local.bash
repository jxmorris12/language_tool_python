#!/bin/bash
#
# Test command-line usage.

set -ex

trap "echo -e '\x1b[01;31mFailed\x1b[0m'" ERR

exit_status=0

echo 'This is okay.' | python -m language_tool_python - || exit_status=1
echo 'This is noot okay.' | python -m language_tool_python - && exit_status=1

echo 'This is okay.' | python -m language_tool_python - || exit_status=1
echo 'This is noot okay.' | python -m language_tool_python - && exit_status=1

echo 'These are “smart” quotes.' | python -m language_tool_python - || exit_status=1
echo 'These are "dumb" quotes.' | python -m language_tool_python - && exit_status=1
echo 'These are "dumb" quotes.' | python -m language_tool_python --enabled-only \
    --enable=EN_QUOTES - && exit_status=1
echo 'These are "dumb" quotes.' | python -m language_tool_python --enabled-only \
    --enable=EN_UNPAIRED_BRACKETS - || exit_status=1

echo '# These are "dumb".' | python -m language_tool_python --ignore-lines='^#' - || exit_status=1

if [[ "$exit_status" == 0 ]]; then
  echo -e '\x1b[01;32mOkay\x1b[0m'
fi
exit "$exit_status"
