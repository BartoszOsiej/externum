Output assets/repl.gif
Set FontSize 18
Set Width 1000
Set Height 600
Set Theme "Molokai"

Type "externum repl"
Enter
Sleep 1s

Type "# Externum REPL — live coding"
Enter
Sleep 500ms

Type "def fib(n):"
Enter
Type "    if n <= 1: return n"
Enter
Type "    return fib(n-1) + fib(n-2)"
Enter
Sleep 500ms

Type ""
Enter
Sleep 300ms

Type "print([fib(i) for i in range(12)])"
Enter
Sleep 1s

Type ""
Enter
Type "# Python readability + compiler power"
Enter
Sleep 500ms

Type "class Animal:"
Enter
Type "    def __init__(self, name):"
Enter
Type "        self.name = name"
Enter
Type "    def speak(self):"
Enter
Type "        return f'{self.name} speaks'"
Enter
Sleep 500ms

Type ""
Enter
Type "print(Animal('Externum').speak())"
Enter
Sleep 1.5s

Type ""
Type "exit()"
Enter
Sleep 500ms
