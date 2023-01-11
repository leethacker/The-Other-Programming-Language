import os
import shutil
import sys
import other

fname = sys.argv[1]
fnamenodot = fname[:fname.index('.')]

contents = open(fname).read()
lines = contents.split('\n')
imports = [fname]
for l in lines:
    l = l.strip()
    if len(l) and l[0] == '<' and '.' in l:
        imports.append(l[1:])

othercdir = os.path.dirname(os.path.realpath(__file__))
cwd = os.getcwd()
os.chdir(othercdir)
def copyover(fname):
    shutil.copyfile(f'{cwd}/{fname}', f'{othercdir}/{fname}')
for f in imports : copyover(f)
other.default(fname)
shutil.copyfile(f'{othercdir}/{fnamenodot}', f'{cwd}/{fnamenodot}')
