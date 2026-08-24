Output assets/compile.gif
Set FontSize 18
Set Width 1000
Set Height 500
Set Theme "Molokai"

Type "externum examples/hello.ext"
Enter
Sleep 1s

Type "externum examples/hello.ext --target python -o hello.py"
Enter
Sleep 1s

Type "externum examples/hello.ext --target bash"
Enter
Sleep 1s

Type "cat hello.py"
Enter
Sleep 1s

Type "# Three targets from one source:"
Enter
Type "# Python / Bash / Binary"
Enter
Sleep 1.5s
