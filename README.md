# The Other Programming Language
It's lower level than C but has vectors.

Run

    python3 ./src/otherc.py otherfilename

to compile Other programs.

## Features

Strings are vectors in Other. Vectors have special standard library functions that begin with v.

    putc vget "hi" 0 #will print h

Other has very simple functions for reading files.

    puts readfile "helloworld.ot"

Public Other functions start with > in their declaration.

    >getc:
    
Importing files is done with <

    <somefile.ot
    
The ^ operator works like a switch case.

    factorial n : n ^ 0 : 1, _ : n * factorial n - 1
