# The Other Programming Language
It's lower level than C but has vectors.

Setup:

Run in src folder

    gcc -c file.c

and

    gcc -c times.c

to setup object files.

Install NASM using your package manager if you don't have it already.

Run

    python3 ./src/otherc.py otherfilename

to compile Other programs.

## Features

Strings are vectors in Other. Vectors have special standard library functions that begin with v.

    putc vget "hi" 0 #will print c

You can initialize vectors with vec which is useful for functions that take in a vector to fill.

    puts readfile vec "helloworld.ot"
