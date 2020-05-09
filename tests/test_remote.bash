#!/bin/bash

set -eux

readonly port=8081
readonly jar='./language_tool_python/LanguageTool-*/languagetool-server.jar'

java -cp $jar org.languagetool.server.HTTPServer --port "$port" &
java_pid=$!
sleep 5

clean ()
{
    kill "$java_pid"
}
trap clean EXIT

echo 'This is okay.' | \
    python -m language_tool_python --remote-host localhost --remote-port "$port" -

! echo 'This is noot okay.' | \
    python -m language_tool_python --remote-host localhost --remote-port "$port" -
