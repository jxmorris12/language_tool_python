#!/bin/bash

set -eux

readonly port=8081
readonly ltp_path=$(printf "import language_tool_python\nprint(language_tool_python.utils.get_language_tool_download_path())\n" | python)
readonly jar="${ltp_path}/LanguageTool-*/languagetool-server.jar"

java -cp $jar org.languagetool.server.HTTPServer --port "$port" &
java_pid=$!
sleep 5

clean ()
{
    kill "$java_pid"
}
trap clean EXIT

exit_status=0

echo 'This is okay.' | \
    python -m language_tool_python --remote-host localhost --remote-port "$port" - || exit_status=1

echo 'This is noot okay.' | \
    python -m language_tool_python --remote-host localhost --remote-port "$port" - && exit_status=1

exit "$exit_status"
