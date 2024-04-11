#!/bin/bash
#
# Test command-line usage.

set -ex

failed_message='\x1b[01;31mFailed\x1b[0m'
trap "echo -e ${failed_message}" ERR

exit_status=0

echo 'This is okay.' | python -m language_tool_python - || exit_status=1
echo 'This is noot okay.' | python -m language_tool_python - && exit_status=1

echo 'This is okay.' | python -m language_tool_python --enabled-only \
    --enable=MORFOLOGIK_RULE_EN_US - || exit_status=1
echo 'This is noot okay.' | python -m language_tool_python --enabled-only \
    --enable=MORFOLOGIK_RULE_EN_US - && exit_status=1

echo 'These are “smart” quotes.' | python -m language_tool_python - || exit_status=1
echo 'These are "dumb" quotes.' | python -m language_tool_python - || exit_status=1
echo 'These are "dumb" quotes.' | python -m language_tool_python --enabled-only \
    --enable=EN_QUOTES - || exit_status=1
echo 'These are "dumb" quotes.' | python -m language_tool_python --enabled-only \
    --enable=EN_UNPAIRED_BRACKETS - || exit_status=1

echo '# These are "dumb".' | python -m language_tool_python --ignore-lines='^#' - || exit_status=1

if [[ "$exit_status" == 0 ]]; then
  echo -e '\x1b[01;32mOkay\x1b[0m'
else
  echo -e $failed_message
fi
exit "$exit_status"
