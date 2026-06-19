Output language_tool_python_demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 750
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 50ms
Set PlaybackSpeed 1.0

Hide
# Need a venv with language_tool_python in current dir
Type "source venv/bin/activate"
Enter

Type "clear"
Enter

Type "python3"
Enter
Wait@30s />>>\s*$/
Show

Type "import language_tool_python"
Enter
Wait@30s />>>\s*$/

Type `tool = language_tool_python.LanguageTool("en-US")`
Enter
Wait@30s />>>\s*$/

Type `text = "I wentt to new york last week."`
Enter
Wait@30s />>>\s*$/

Type "tool.check(text)"
Enter
Wait@30s />>>\s*$/

Type "tool.correct(text)"
Enter
Wait@30s />>>\s*$/

Type "tool.close()"
Enter
Wait@30s />>>\s*$/

Type `tool_fr = language_tool_python.LanguageTool("fr")`
Enter
Wait@30s />>>\s*$/

Type `tool_fr.correct("Je suis aller au marché hier.")`
Enter
Wait@60s />>>\s*$/
Sleep 10s

Hide
Type "exit()"
Enter

Type "clear"
Enter
Show

Type "cat sample.txt"
Enter
Wait@60s />\s*$/

Type "language_tool_python -l en-US --apply sample.txt"
Enter
Wait@60s />\s*$/
Sleep 10s
