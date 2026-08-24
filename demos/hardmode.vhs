Output assets/hardmode.gif
Set FontSize 18
Set Width 1000
Set Height 600
Set Theme "Molokai"

Type "externum run examples/hardcore.ext --hard"
Enter
Sleep 1s

Type "# NV2.0 Hard Mode:"
Enter
Type "# Mandatory declarations, ownership, traits, macros"
Enter
Sleep 500ms

Type "# === Ownership ==="
Enter
Type "p: Ptr[Int] = alloc(Int)"
Enter
Type "@p = 42"
Enter
Type "print(@p)"
Enter
Type "free(p)"
Enter
Sleep 1s

Type ""
Type "# === Traits ==="
Enter
Type "trait Speaker:"
Enter
Type "    def speak(self) -> Str"
Enter
Sleep 500ms

Type ""
Type "impl Speaker for Dog:"
Enter
Type "    def speak(self) -> Str:"
Enter
Type "        return 'woof'"
Enter
Sleep 1s

Type ""
Type "# Compile-time safety — no runtime segfaults"
Enter
Sleep 1.5s
