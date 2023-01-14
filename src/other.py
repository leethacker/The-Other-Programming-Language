import re
import sys
import subprocess

tocompile = []
compiled = []
asmfiles = []
objfiles = []

tokens = []
ln = 1
output = ''
dataoutput = ''
initoutput = ''
bssoutput = ''
inmacro = []
macros = {}
macroargs = {}
pushedtoks = []
funcs = {}
variables = {}
stk = []
defers = []
deferblocks = []
breaklist = []
globalvars = {}
callables = {}
unreturnables = []

def isint(n):
    try:
        int(n)
        return True
    except: 
        if n[0] == "'" and n[-1] == "'" : return True
        return False

def toint(n):
    return int(n)

def gettokens(s):
    result = re.findall(r'###[^#]*###|#[^\n]*\n ?|%\{[^\}]*\}|%r[\w]+|[\w]+|\'.\'|\-\>|\+\+|\-\-|==|!=|>=|<=|\\!|\+=|\-=|\*=|\-@|\-~|\+~|\*~|\?~|@~|:=|&&|\|\||><|!><|~ *\(\)|"[^"]*"|`[^`]*`|\S|\n |\n', s)
    result = [r if r[0] != '#' else '\n' + (' ' if r[-1] == ' ' else '') for r in result]
    nr = []
    lastt = '\n'
    for t in result[::-1]:
        if lastt[0] == '\n' and t == '\n' : nr.append('\n ')
        else : nr.append(t)
        lastt = t
    result = nr[::-1]
    return result

def err(s):
    m = ''
    if inmacro : m = f' in macro {inmacro[-1]}'
    snip = ' '.join(prevtoks[-5:]) + ' ' + ' '.join(tokens[::-1][:3])
    print(f"Error at line {ln}{m}: {s} in '{snip}'")
    int('a')
    sys.exit(0)

def flatten(l):
    return [item for sublist in l for item in sublist]

def toptok():
    global tokens
    global inmacro
    global ln
    result = tokens[-1]
    #print(result)
    if result == ';' : result = '\n '
    elif result == '-~' : result = str(ln)
    elif result == '?~' : result = genid()
    if re.match(r'~ *\(\)', tokens[-2]):
        tokens.pop()
        tokens.pop()
        if inmacro : inmacro.pop()
        if inmacro : inmacro.pop()
        if result in macros:
            #print(result, macros)
            macros.pop(result)
            macroargs.pop(result)
        return toptok()
    if isint(result) and tokens[-2] == '*~':
        times = int(toint(result))
        tokens.pop()
        tokens.pop()
        if inmacro : inmacro.pop()
        if inmacro : inmacro.pop()
        match('(')
        depth = 1
        toks = []
        while depth > 0:
            if toptok() == '(' : depth += 1
            elif toptok() == ')' : depth -= 1
            if depth > 0 : toks.append(getok())
            else : getok()
        for i in range(times):
            tokens += toks[::-1]
        return toptok()
    if result in macros:
        if result in inmacro[:-2]:
            err(f"recursive macro '{result}'")
        #print(macros)
        tokens.pop()
        args = macroargs[result]
        argsmap = {}
        spread = False
        for a in args:
            argsmap[a] = []
            depth = 0
            if toptok() == '(':
                depth += 1
                getok()
            else:
                if toptok() == '\n ':
                    spread = True
                    break
                argsmap[a].append(getok())
            while depth > 0:
                if toptok() == '(' : depth += 1
                elif toptok() == ')' : depth -= 1
                if depth > 0 : argsmap[a].append(getok())
                else : getok()
        if spread:
            oldln = ln
            spreadlist = []
            spreadpos = 0
            firstline = True
            while toptok() == '\n ' : getok()
            while firstline or toptok() == '\n ':
                firstline = False
                if toptok() == '\n ' : getok()
                #print(f'"{toptok()}"')
                if toptok()[0] == '\n' : break
                l = []
                while toptok()[0] != '\n':
                    t = getok()
                    if t == '@~' : t = str(spreadpos)
                    l.append(t)
                spreadlist.append(l)
                spreadpos += 1
            ends = toptok()
            res = []
            for i in range(len(spreadlist)):
                l = spreadlist[::-1][i]
                if l:
                    nl = [ends] + l[::-1] + flatten([argsmap[a][::-1] for a in args[::-1] if a in argsmap]) + [result]
                    nl = [str(len(spreadlist) - i - 1) if t == '@~' else t for t in nl]
                    res += nl
            tokens += res
            #print(res, toptok())
            ln = oldln + 1
            return toptok()
        else:
            tocombine = None
            res = []
            for t in macros[result]:
                if tocombine:
                    if t in args : res += argsmap[t][::-1]
                    else : res.append(t)
                    tp = res.pop()
                    res.append(tocombine + tp)
                    tocombine = None
                elif t in args : res += argsmap[t]#[::-1]
                elif t == '+~' : tocombine = res.pop()
                else : res.append(t)
            #print(res)
            tokens += res[::-1]
            inmacro += [result] * len(res)
            #print(tokens)
            return toptok()
    return result

prevtoks = []
def getok():
    global ln
    result = toptok()
    tok = tokens.pop()
    prevtoks.append(result)
    if len(inmacro) : inmacro.pop()
    if tok[0] == '\n' : ln += 1
    return result

def expect(a, b):
    err(f"expected '{a}' found '{b}'")

def match(s):
    g = getok()
    if g != s:
        expect(s, g)

def matchinplace(s):
    g = toptok()
    if g != s:
        expect(s, g)

def pushtoks():
    pushedtoks.append(tokens[:])

def poptoks():
    global tokens
    tokens = pushedtoks.pop()

def skipnl():
    while toptok() in ['\n', '\n '] : getok()

labeli = 0
def newlabel(s):
    global labeli
    result = f'label_{s}~{labeli}'
    labeli += 1
    return result

def outlabel(s):
    global output
    output += s + ':\n'

def out(s):
    global output
    output += ' ' * 4 + s + '\n'

def dataout(s):
    global dataoutput
    dataoutput += ' ' * 4 + s + '\n'

def initout(s):
    global initoutput
    initoutput += ' ' * 4 + s + '\n'

def bssout(s):
    global bssoutput
    bssoutput += ' ' * 4 + s + '\n'

allregs = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9', 'rbx', 'rbp', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15']
freeregs = allregs[::-1]
retreg = 'rax'

opmap = {
    '+' : 'add',
    '-' : 'sub',
    '*' : 'imul',
}

divopmap = {
    '/' : 'idiv',
    '%' : 'idiv',
}

cmpops = {
    '==' : 'e',
    '!=' : 'ne',
    '<' : 'l',
    '>' : 'g',
    '<=' : 'le',
    '>=' : 'ge',
}

def getid():
    t = getok()
    if not isid(t) : expect('identifier', t)
    return t

def getint():
    t = getok()
    if not isint(t) : expect('int', t)
    return t

def getvar():
    ve = getid()
    if not ve in variables : variables[ve] = getfreereg()
    return ve

def isusedreg(r):
    return r in allregs and not r in freeregs

def getfreereg(pref=[]):
    if len(freeregs) == 0:
        for v in variables.copy():
            if variables[v]:
                push(v)
                freeregs.append(variables[v])
                variables.pop(v)
    for r in pref:
        if r in freeregs:
            return freeregs.pop(freeregs.index(r))
    return freeregs.pop()

def freereg(r):
    if not r in freeregs and r in allregs and not r in variables.values() : freeregs.append(r)

def freeregsinlist(rl):
    for r in rl: freereg(r)

def freeregsbyvar(rl):
    for r in rl:
        if r in variables:
            freereg(variables[r])
            variables.pop(r)

def movto(a, b):
    if a == b : return a
    out(f'mov {a}, {b}')
    return a

def movvto(a, b):
    return movto(a, varloc(b))

def isusingid(id):
    return id in funcs or id in variables or id in globalvars

def isalnum(id):
    return re.match(r'[\w_]+', id)

def isid(id):
    return isalnum(id) and not isint(id)

def pushreg(r):
    stk.append(None)
    out(f'push qword {r}')

def popreg(v):
    stk.pop()
    out(f'pop qword {v}')

def push(v):
    out(f'push qword {varloc(v)}')
    stk.append(v)

def pop(v):
    stk.pop()
    out(f'pop qword {varloc(v)}')

def varlocstk(v):
    if v in stk : return f'qword [rsp + {stk[::-1].index(v) * 8}]'

def varlocstkfirst(v):
    if v in stk : return varlocstk(v)
    elif v[0] == '%' : return v[1:]
    return variables[v]

def varloc(v):
    #if v in variables : return variables[v]
    #else : return varlocstk(v)
    return varlocstkfirst(v)

def docallold(lambdavar=None):
    name = getok() if not lambdavar else lambdavar
    oldvars = variables.copy()
    varkeys = list(variables.keys())
    usedregs = [r for r in allregs if isusedreg(r)]
    for r in usedregs:
        if r in variables.values():
            push(list(variables.keys())[list(variables.values()).index(r)])
        else : pushreg(r)
        #pushreg(r)
    regs = allregs[::-1]
    if lambdavar:
        if toptok() == '(':
            getok()
            while toptok() != ')':
                r = regs.pop()
                movto(r, expr())
            getok()
        else:
            r = regs.pop()
            movto(r, expr())
        out(f'mov {retreg}, {varloc(lambdavar)}')
        out(f'call {retreg}')
    else:
        args = funcs[name] if name in funcs else callables[name]
        argregs = []
        for a in args:
            e = donot()
            pushreg(e)
            argregs.append(regs.pop())
        for a in args:
            popreg(argregs.pop())
            #if r in freeregs : freeregs.pop(freeregs.index(r))
            #movto(r, donot()) #expr()
        out(f'call {name}')
    for v in usedregs[::-1]:
        popreg(v)
    return retreg

def docall(lambdavar=None):
    if lambdavar : return docallold(lambdavar=lambdavar)
    name = getok() if not lambdavar else lambdavar
    args = funcs[name] if name in funcs else callables[name]
    regs = allregs[::-1]
    argregs = []
    for a in args:
        argregs.append(regs.pop())
    for a in args:
        e = donot()
        pushreg(e)
    usedregs = [r for r in allregs if isusedreg(r)]
    for r in usedregs:
        pushreg(r)
    for i in range(len(argregs)):
        #popreg(argregs.pop())
        r = argregs[::-1][i]
        movto(r, f'qword [rsp + {(len(usedregs) + i) * 8}]')
    cbuf = len(stk) % 2 == 0
    if cbuf : pushreg('0')
    out(f'call {name}')
    if cbuf:
        stk.pop()
        out('add rsp, 8')
    for v in usedregs[::-1]:
        popreg(v)
    for v in args : stk.pop()
    out(f'add rsp, {len(args) * 8}')
    return retreg

def doparens():
    getok()
    if toptok() == '\\':
        return dolambda()
    skipnl()
    e = startline() #if toptok() == '<' else expr()
    skipnl()
    while toptok() != ')':
        skipnl()
        e = startline() #if toptok() == '<' else expr()
        skipnl()
    match(')')
    return e

def docrement(v):
    op = getok()[:-1]
    e = expr()
    r = varloc(v)
    rr = r
    regr = r in allregs
    if not regr:
        rr = getfreereg()
        movto(rr, r)
    out(f'{opmap[op]} {rr}, {e} ; shorthand op')
    if not regr:
        movto(r, rr)
        freereg(rr)
    return r

def dovar():
    name = getok()
    if toptok() == '=' : return doassign(name, [])
    elif toptok()[-1] == '=' and toptok()[:-1] in opmap : return docrement(name)
    return varloc(name)

def doindexopassign(arr, ind, cell):
    op = getok()[:-1]
    e = expr()
    r = getfreereg()
    out(f'mov {r}, [{arr} + {ind} * {cell}]')
    out(f'{opmap[op]} {r}, {e}')
    out(f'mov [{arr} + {ind} * {cell}], {r}')
    freereg(r)
    freereg(arr)
    freereg(ind)
    return r

def doindexassign(arr, ind, cell):
    getok()
    e = expr()
    word = 'qword'
    ex = e
    if cell == '1':
        out(f'mov rax, {e}')
        ex = 'al'
        word = 'byte'
    out(f'mov {word} [{arr} + {ind} * {cell}], {ex} ; index assignment')
    freereg(arr)
    freereg(ind)
    return e

def doindex(arr):
    getok()
    arr = movtoreg(arr)
    ind = expr()
    ind = movtoreg(ind)
    cell = '8'
    if toptok() != ']':
        cell = getint()
    match(']')
    if toptok() == '=' : return doindexassign(arr, ind, cell)
    elif toptok()[-1] == '=' and toptok()[:-1] in opmap:
        return doindexopassign(arr, ind, cell)
    out(f'mov {retreg}, [{arr} + {ind} * {cell}]')
    if cell == '1':
        out(f'and {retreg}, 0xff')
    freereg(arr)
    freereg(ind)
    return retreg

def isvar(v):
    #return v in variables
    print(v)
    try:
        varloc(v)
        return not isint(v)
    except : return False

def doincdecarr(v, ins):
    getok()
    arr = v
    arr = movtoreg(arr)
    ind = expr()
    ind = movtoreg(ind)
    cell = '8'
    if toptok() != ']':
        cell = getint()
    match(']')
    r = freeregs.pop()
    out(f'mov {r}, [{arr} + {ind} * {cell}]')
    out(f'{ins} {r}, 1')
    tomov = r
    if cell == '1':
        out(f'and {r}, 0xff')      
        out(f'mov {retreg}, {r}')
        tomov = 'al'
    out(f'mov [{arr} + {ind} * {cell}], {tomov}')
    freereg(r)
    freereg(arr)
    freereg(ind)
    return r

def doincdec():
    op = getok()
    ins = opmap[op[0]]
    if toptok() in variables:
        v = getvar()
        if toptok() == '[' : return doincdecarr(varloc(v), ins)
        out(f'{ins} {varloc(v)}, 1')
        return varloc(v)
    elif toptok() in globalvars:
        glabel = globalvars[getok()]
        out(f'mov {retreg}, {glabel}')
        out(f'mov {retreg}, [{retreg}]')
        if toptok() == '[' : return doincdecarr(retreg, ins)
        out(f'{ins} {retreg}, 1')
        r = freeregs.pop()
        out(f'mov {r}, {glabel}')
        out(f'mov [{r}], {retreg}')
        freeregs.append(r)
        return retreg
    else : expect('variable', toptok())

def donegate():
    getok()
    e = expr()
    if not e in allregs:
        r = getfreereg()
        movto(r, e)
        e = r
    if isint(e) : return '-' + str(toint(e))
    out(f'imul {e}, -1')
    return e

def doexeclambda():
    getok()
    e = expr()
    l = newlabel('lambda')
    variables[l] = getfreereg()
    out(f'mov {varloc(l)}, {e}')
    return docall(lambdavar=l)

def dostr():
    lit = getok()
    s = lit[1:-1]
    escaped = False
    label = newlabel('strlit')
    asm = f'{label} db '
    for c in s:
        val = ord(c)
        if escaped:
            escmap = {'0' : 0, 'n' : 10, 't' : 12}
            if c in escmap : val = escmap[c]
            escaped = False
            asm += str(val) + ', '
        elif c == '\\' : escaped = True
        else : asm += str(val) + ', '
    asm += '0,'
    dataout(asm)
    out(f'mov {retreg}, {label}')
    return retreg

vsi = 0
def dovstr():
    global tokens
    global vsi
    lit = getok()
    s = lit[1:-1]
    escaped = False
    l = f'__uihwdbwbidkkj_STRVAR_UNIQUE_{vsi}__'
    vsi += 1
    newtokens = ['(', 'vinit', l, ';', 'vfill', l, ';']
    for c in s:
        val = ord(c)
        if escaped:
            escmap = {'0' : 0, 'n' : 10, 't' : 12}
            if c in escmap : val = escmap[c]
            escaped = False
            newtokens += [str(val), ';']
        elif c == '\\' : escaped = True
        newtokens += [str(val), ';']
    newtokens += [';', ';', l, ')']
    if len(s) == 0 : newtokens = ['vec']
    tokens += newtokens[::-1]
    return term()

def getfp():
    getok()
    name = getid()
    if not name in funcs : expect('function', name)
    out(f'mov {retreg}, {name}')
    return retreg

def dobreak():
    getok()
    out(f'jmp {breaklist[-1]}')
    return '0'

def doln():
    getok()
    return str(ln)

def doglobalopassign(name):
    op = getok()[:-1]
    e = expr()
    r = freeregs.pop()
    glabel = globalvars[name]
    out(f'mov {r}, qword {glabel}')
    out(f'mov {r}, qword [{r}]')
    out(f'{opmap[op]} {r}, {e}')
    out(f'mov {retreg}, {glabel}')
    out(f'mov qword [{retreg}], {r}')
    freeregs.append(r)
    return r

def doglobal():
    name = getok()
    if toptok() == ':=' : return doglobalassign(name)
    elif toptok()[-1] == '=' and toptok()[:-1] in opmap:
        return doglobalopassign(name)
    glabel = globalvars[name]
    out(f'mov {retreg}, qword {glabel}')
    out(f'mov {retreg}, qword [{retreg}]')
    return retreg

def dounret():
    getok()
    ur = getvar()
    unreturnables.append(ur)

def isvar(v):
    try:
        varloc(v)
        return True
    except : return False

def unretmap():
    return {varloc(v) : v for v in unreturnables if isvar(v)}

def doasm():
    block = getok()
    asm = block[2:-1]
    out(asm)
    return retreg

def term():
    if isint(toptok()) : result = getok()
    elif toptok() == '(' : result = doparens()
    elif toptok() == '@' : result = doloop()
    elif toptok() == '?' : result = doif()
    elif toptok() in ['++', '--'] : result = doincdec()
    elif toptok() == '-' : result = donegate()
    elif toptok() == '\\' : result = getfp()
    elif toptok() == '\\!' : result = doexeclambda()
    elif toptok() == '-@' : result = dobreak()
    elif toptok() == '><' : result = doret()
    elif toptok() == '!><' : result = dounret()
    elif toptok() == '->' : result = dodefer()
    #elif toptok() == '-~' : result = doln()
    elif toptok()[0] == '"' and toptok()[-1] == '"' : result = dovstr()
    elif toptok()[0] == '`' and toptok()[-1] == '`' : result = dostr()
    elif toptok()[0:2] == '%{' : result = doasm()
    elif isvar(toptok()) : result = dovar() 
    elif toptok() in funcs : result = docall() 
    elif toptok() in callables : result = docall()
    elif toptok() in globalvars : result = doglobal()
    else: 
        t = getok()
        if toptok() == ':=' : result = doglobalassign(t)
        elif toptok() == '=' : result = doassign(t, [])
        else : err(f"malformed term '{t}'")
    while toptok() == '[' : result = doindex(result)
    #if result == retreg : result = movtoreg(result)
    return result

def dodivop(op, var, val):
    used = ['rax', 'rcx', 'rdx']
    for r in used:
        out(f'push qword {r}')
        #stk.append('%' + r)
        stk.append(None)

    out('mov rax, {}'.format((var)))
    out('mov rcx, {}'.format((val)))
    out('xor rdx, rdx')
    if op == '%32' : out('idiv ecx')
    else : out('idiv rcx')
    om = {'/' : 'rax', '%' : 'rdx', '%32' : 'rdx'}
    out('mov {}, {}'.format((var), om[op]))

    for r in used[::-1]:
        if (r) != (var) : out('pop qword {}'.format((r)))
        else : out('add rsp, 8')
        #out('pop qword {}'.format((r)))
        stk.pop()

    return var

def infix():
    e = term()
    accum = None
    while toptok() in opmap or toptok() in divopmap:
        if not accum:
            accum = getfreereg([e])
            movto(accum, e)
        op = getok()
        e = term()
        if not e in allregs:
            r = getfreereg()
            out(f'mov {r}, {e}')
            e = r
        if op in opmap : out(f'{opmap[op]} {accum}, {e} ; infix op')
        elif op in divopmap : dodivop(op, accum, e)
        e = accum
    return e

def donot():
    invert = toptok() == '!'
    if invert : getok()
    e = infix()
    if invert:
        e = movtoreg(e)
        skip = newlabel('skip')
        exitl = newlabel('exit')
        out(f'test {e}, {e}')
        out(f'jne {skip}')
        out(f'mov {retreg}, 1')
        out(f'jmp {exitl}')
        outlabel(skip)
        out(f'xor {retreg}, {retreg}')
        outlabel(exitl)
        e = retreg
    return e

def docmpop():
    e = donot()
    accum = None
    #if e == retreg : e = movtoreg(e)
    # accum = donot()
    # accum = movtoreg(accum)
    # e = accum
    while toptok() in cmpops:
        if not accum:
            accum = getfreereg([e])
            movto(accum, e)
        op = getok()
        e = donot()
        nextlabel = newlabel('next')
        exitlabel = newlabel('exit')
        out(f'xor {retreg}, {retreg}')
        out(f'cmp {accum}, {e}')
        # out(f'cmov{cmpops[op]} {retreg}, rsp')
        out(f'set{cmpops[op]} al')
        out(f'mov {accum}, {retreg}')
        # out(f'xor {accum}, {accum}')
        # out(f'j{cmpops[op]} {nextlabel}')
        # out(f'jmp {exitlabel}')
        # outlabel(nextlabel)
        # out(f'mov {accum}, 1')
        # outlabel(exitlabel)
        e = accum
    return e

def doand():
    f = docmpop
    e = f()
    if toptok() != '&&' : return e
    exitlabel = newlabel('exit')
    while toptok() == '&&':
        e = movtoreg(e)
        out(f'test {e}, {e}')
        out(f'je {exitlabel}')
        getok()
        e = f()
        e = movtoreg(e)
        out(f'test {e}, {e}')
        out(f'je {exitlabel}')
    finishedlabel = newlabel('finished')
    out(f'mov {retreg}, 1')
    out(f'jmp {finishedlabel}')
    outlabel(exitlabel)
    out(f'xor {retreg}, {retreg}')
    outlabel(finishedlabel)
    return retreg

def door():
    f = doand
    e = f()
    if toptok() != '||' : return e
    exitlabel = newlabel('exit')
    while toptok() == '||':
        e = movtoreg(e)
        out(f'test {e}, {e}')
        out(f'jne {exitlabel}')
        getok()
        e = f()
        e = movtoreg(e)
        out(f'test {e}, {e}')
        out(f'jne {exitlabel}')
    finishedlabel = newlabel('finished')
    out(f'xor {retreg}, {retreg}')
    out(f'jmp {finishedlabel}')
    outlabel(exitlabel)
    out(f'mov {retreg}, 1')
    outlabel(finishedlabel)
    return retreg

def doif():
    global variables
    global freeregs
    global deferblocks
    olddeferblocks = deferblocks[:]
    deferblocks = []
    if toptok() == '?':
        getok()
        skipnl()
        oldvars = variables.copy()
        oldfreeregs = freeregs.copy()
        exitl = newlabel('exit')

        nxtcmp = newlabel('nxtcmp')
        n = expr()#toint(toptok())
        n = movtoreg(n)
        if deferblocks:
            pushreg(n)
            dodeferblocks()
            deferblocks = []
            popreg(n)
        #getok()
        match(':')
        out(f'test {n}, {n}')
        freereg(n)
        out(f'je {nxtcmp}')
        r = expr()
        movto(retreg, r)
        dodeferblocks()
        deferblocks = []
        out(f'jmp {exitl}')
        outlabel(nxtcmp)

        if toptok() == ',':
            getok()
            skipnl()
            while toptok() != '_':
                nxtcmp = newlabel('nxtcmp')
                n = expr()#toint(toptok())
                n = movtoreg(n)
                if deferblocks:
                    pushreg(n)
                    dodeferblocks()
                    deferblocks = []
                    popreg(n)
                #getok()
                match(':')
                out(f'test {n}, {n}')
                freereg(n)
                out(f'je {nxtcmp}')
                freeregs = oldfreeregs[:]
                r = expr()
                movto(retreg, r)
                dodeferblocks()
                deferblocks = []
                out(f'jmp {exitl}')
                freeregs = oldfreeregs[:]
                match(',')
                while toptok() == '\n ' : getok()
                variables = oldvars.copy()
                outlabel(nxtcmp)
            getok()
            match(':')
            r = expr()
            dodeferblocks()
            movto(retreg, r)
        variables = oldvars.copy()
        outlabel(exitl)
        deferblocks = olddeferblocks
        return retreg

def domatch():
    global variables
    global freeregs
    global deferblocks
    e = door()
    if toptok() == '^':
        olddeferblocks = deferblocks[:]
        deferblocks = []
        getok()
        skipnl()
        oldvars = variables.copy()
        oldfreeregs = freeregs.copy()
        exitl = newlabel('exit')
        movto(retreg, e)
        e = retreg
        while toptok() != '_':
            nxtcmp = newlabel('nxtcmp')
            n = expr()#toint(toptok())
            if deferblocks:
                pushreg(n)
                dodeferblocks()
                deferblocks = []
                popreg(n)
            #getok()
            match(':')
            out(f'cmp {e}, {n}')
            out(f'jne {nxtcmp}')
            r = expr()
            movto(retreg, r)
            dodeferblocks()
            out(f'jmp {exitl}')
            match(',')
            while toptok() == '\n ' : getok()
            variables = oldvars.copy()
            outlabel(nxtcmp)
            freeregs = oldfreeregs[:]
        getok()
        match(':')
        r = expr()
        movto(retreg, r)
        dodeferblocks()
        variables = oldvars.copy()
        outlabel(exitl)
        freeregs = oldfreeregs[:]
        deferblocks = olddeferblocks
        return retreg
    return e

def expr():
    global freeregs
    oldfreeregs = freeregs[:]
    result = domatch()
    if toptok() == '[' : result = doindex(result)
    #freeregs = oldfreeregs
    return result

idi = 0
def genid():
    global idi
    result = f'__UNIQUE_ID__{idi}__'
    idi += 1
    return result

def domacro(name, args):
    def toptok():
        t = tokens[-1]
        if t == '-~' : t = str(ln)
        #elif t == '?~' : t = genid()
        return t
    def getok():
        result = toptok()
        if inmacro : inmacro.pop()
        tokens.pop()
        return result
    getok()
    toks = []
    if toptok() == '(':
        getok()
        depth = 1
        while depth > 0:
            if toptok() == '(' : depth += 1
            elif toptok() == ')' : depth -= 1
            if depth > 0:
                t = getok()
                toks.append(';' if t == '\n ' else t)
            else : getok()
    else:
        while toptok() != '\n':
            t = getok()
            toks.append(';' if t == '\n ' else t)
        while toks and toks[-1] == ';' : toks.pop()
    macros[name] = toks
    macroargs[name] = args
    return 0

def dodeferblocks():
    global tokens
    global deferblocks
    if deferblocks:
        out(';defers')
        out(f'push {retreg}')
        stk.append(None)
        #for d in defers[::-1]:
        #    out(f'call {d}')    
        for d in deferblocks:
            tokens += d[::-1]
            startline()
        stk.pop()
        out(f'pop {retreg}')
        deferblocks = []
    

def dofunc(name, args, exportstatus):
    global freeregs
    global variables
    global defers
    global stk
    global tokens
    global deferblocks
    global unreturnables
    oldfreeregs = freeregs[:]
    oldvars = variables.copy()
    olddefers = defers[:]
    olddeferblocks = deferblocks[:]
    oldstk = stk[:]
    freeregs = allregs[::-1]
    stk = []
    variables = {}
    defers = []
    deferblocks = []
    unreturnables = []
    getok()
    if exportstatus : out(f'{exportstatus} {name}')
    funcs[name] = args
    leave = newlabel('exitfunc')
    out(f'jmp {leave}')
    outlabel(name)
    for a in args:
        variables[a] = freeregs.pop()
    while len(tokens) > 1 and toptok() == '\n ' : getok()
    while len(tokens) > 2 and toptok() not in ['\n', ')']:
        r = startline()
        while len(tokens) > 1 and toptok() == '\n ' : getok()
    urlocs = unretmap()
    if r in urlocs:
        err(f"Variable '{urlocs[r]}' is unreturnable")
    movto(retreg, r)
    #matchinplace('\n')
    if deferblocks:
        out(f'push {retreg}')
        stk.append(None)
        #for d in defers[::-1]:
        #    out(f'call {d}')    
        for d in deferblocks:
            tokens += d[::-1]
            startline()
        stk.pop()
        out(f'pop {retreg}')
    if stk:
        out(f'add rsp, {8 * len(stk)}')
        stk = []
    out('ret')
    outlabel(leave)
    out(f'mov {retreg}, {name}')
    freeregs = oldfreeregs
    variables = oldvars
    defers = olddefers[:]
    deferblocks = olddeferblocks
    stk = oldstk
    return retreg

def doret():
    global stk
    getok()
    e = expr()
    urlocs = unretmap()
    if e in urlocs:
        err(f"Variable '{urlocs[e]}' is unreturnable")
    movto(retreg, e)
    if defers:
        out(f'push {retreg}')
        stk.append(None)
        for d in defers[::-1]:
            out(f'call {d}')
        stk.pop()
        out(f'pop {retreg}')
    if stk:
        out(f'add rsp {8 * len(stk)}')
        stk = []
    out('ret')
    return '0'

def dolambda():
    getok()
    args = []
    while toptok() != ':':
        args.append(getid())
    #getok()
    dofunc(newlabel('lambda'), args, None)
    match(')')
    return retreg

def idorexpr():
    var = toptok()
    if not isid(var) : return expr()
    if not var in variables:
        variables[var] = getfreereg()
    return expr()

def doarr():
    global freeregs
    getok()
    arrname = newlabel('array')
    cell = '8'
    dmap = {'1' : 'db', '8' : 'dq'}
    resmap = {'1' : 'resb', '8' : 'resq'}
    if toptok() == '%':
        getok()
        cell = getint()
    s = f'{arrname} {dmap[cell]} '
    length = 0
    f = dataout
    if toptok() == '^':
        getok()
        length = getint()
        s = f'{arrname} {resmap[cell]} {length}'
        f = bssout
    else:
        oldregs = freeregs[:]
        tmpreg = getfreereg()
        out(f'mov {tmpreg}, {arrname}')
        while not toptok() in [']', ':']:
            t = toptok()
            if isint(t):
                s += t + ', '
            else:
                s += '0, '
            skipnl()
            e = expr()
            skipnl()
            if e != t or not isint(t):
                out(f'mov [{tmpreg} + {length} * {cell}], {e}')
            length += 1
        freeregs = oldregs
    if toptok() == ':':
        getok()
        lv = getvar()
        out(f'mov {varloc(lv)}, {length}')
    match(']')
    f(s)
    out(f'mov {retreg}, {arrname}')
    return retreg

def doloop():
    global deferblocks
    olddeferblocks = deferblocks[:]
    deferblocks = []
    getok()
    if toptok() == '[' : return doarr()
    dirup = True
    if toptok() == '<':
        getok()
        dirup = False
    var = toptok()
    whilestart = newlabel('whilestart')
    outlabel(whilestart)
    ri = idorexpr()
    loopstart = newlabel('loopstart')
    loopexit = newlabel('loopexit')
    breaklist.append(loopexit)
    if toptok() == ':':
        getok()
        #outlabel(loopstart)
        if not ri in allregs:
            r = getfreereg()
            out(f'mov {r}, {ri}')
            ri = r
        if deferblocks:
            pushreg(ri)
            dodeferblocks()
            deferblocks = []
            popreg(ri)
        out(f'test {ri}, {ri}')
        out(f'je {loopexit}')
        result = startline()
        dodeferblocks()
        out(f'jmp {whilestart}')
        outlabel(loopexit)
    else:
        start = 0
        end = expr()
        step = 1
        if toptok() != ':':
            start = end
            end = expr()
        end = movtoreg(end)
        if toptok() != ':':
            step = expr()
        match(':')
        out(f'mov {ri}, {start}')
        out(f'cmp {ri}, {end}')
        out(f'j{"g" if dirup else "l"}e {loopexit}')
        outlabel(loopstart)
        while toptok() == '[':
            getok()
            ve = getvar()
            arr = expr()
            cell = '8'
            if toptok() != ']' : cell = getint()
            out(f'mov {varloc(ve)}, [{arr} + {ri} * {cell}]')
            if cell == '1' : out(f'and {varloc(ve)}, 0xff')
            match(']')
        result = startline()
        dodeferblocks()
        out(f'{"add" if dirup else "sub"} {ri}, {step}')
        out(f'cmp {ri}, {end}')
        out(f'j{"l" if dirup else "g"} {loopstart}')
        outlabel(loopexit)
    breaklist.pop()
    deferblocks = olddeferblocks
    return result

def doassign(name, args):
    getok()
    args = [name] + args
    if name in unreturnables : err(f"cannot reassign '{name}'")
    for a in args:
        if not a in variables:
            variables[a] = getfreereg()
        e = expr()
        urlocs = unretmap()
        if e in urlocs : unreturnables.append(a)
        movto(varloc(a), e)
    return e

def dodefer():
    global deferblocks
    getok()
    tokens = []
    defname = newlabel('defer')
    skip = newlabel('skip')
    #defers.append(defname)
    #out(f'jmp {skip}')
    #outlabel(defname)
    #startline()
    #out('ret')
    while toptok()[0] != '\n':
        tokens.append(getok())
    tokens.append(getok())
    deferblocks.append(tokens)
    outlabel(skip)

def doimport(name):
    name += '.'
    getok()
    postfix = getok()
    name += postfix
    if postfix == 'o' : objfiles.append(name)
    else:
        tocompile.append(name)
        newm, newma = getpublicmacros(name)
        newf, pubfs = getfuncs(name)
        for m in newm:
            macros[m] = newm[m]
        for m in newma:
            macroargs[m] = newma[m]
        for f in pubfs:
            funcs[f] = newf[f]
            callables[f] = newf[f]
            out(f'extern {f}')
    if postfix != 'o':
        l = name.replace('.', '~')
        out(f'extern {l}')
        out(f'call {l}')
        initout(f'call {l}')
    return '0'

def movtoreg(e):
    if not e in allregs:
        r = getfreereg()
        movto(r, e)
        return r
    return e

def doglobalassign(name, toplevel=False):
    global output
    global initoutput
    global tokens
    if toplevel:
        oldoutput = output
        output = initoutput
        oldtokens = tokens[:]
    #f = initout if toplevel else out
    if not name in globalvars:
        glabel = newlabel('global')
        globalvars[name] = glabel
        dataout(f'{glabel} dq 0')
    glabel = globalvars[name]
    getok()
    e = expr()
    e = movtoreg(e)
    out(f'mov {retreg}, {glabel}')
    out(f'mov qword [{retreg}], {e}')
    freereg(e)
    if toplevel:
        initoutput = output
        output = oldoutput
        tokens = oldtokens
        return doglobalassign(name)
    return e

def getpublicmacros(filename):
    global macros
    global macroargs
    global tokens
    global ln
    oldtokens = tokens[:]
    oldmacros = macros.copy()
    oldmacroargs = macroargs.copy()
    oldln = ln
    contents = open(filename).read()
    tokens = gettokens(contents + '\n\n')[::-1]
    macros = {}
    macroargs = {}
    while len(tokens) > 2 and toptok()[0] == '\n' : getok()
    while len(tokens) > 2:
        public = False
        if toptok() == '>':
            public = True
            getok()
        name = getok()
        args = []
        while toptok() not in ['~', '\n', '\n ']:
            args.append(getok())
        if toptok() == '~':
            domacro(name, args)
            if not public:
                macros.pop(name)
                macroargs.pop(name)
        while len(tokens) > 2 and toptok()[0] == '\n' : getok()
    result = (macros, macroargs)
    macros = oldmacros
    macroargs = oldmacroargs
    tokens = oldtokens
    ln = oldln
    return result

def getfuncs(filename):
    global macros
    global macroargs
    global tokens
    global ln
    oldtokens = tokens[:]
    oldmacros = macros.copy()
    oldmacroargs = macroargs.copy()
    oldln = ln
    contents = open(filename).read()
    tokens = gettokens(contents + '\n\n')[::-1]
    funcs = {}
    publicfuncs = []
    while len(tokens) > 2 and toptok()[0] == '\n' : getok()
    while len(tokens) > 2:
        public = False
        args = []
        if toptok() == '>':
            public = True
            getok()
        elif toptok() == '<':
            getok()
        name = getok()
        while toptok() not in [':', '\n'] and len(tokens) > 2:
            args.append(getok())
        if toptok() == ':':
            funcs[name] = args
            if public : publicfuncs.append(name)
            while toptok() != '\n' and len(tokens) > 2 : getok()
        while len(tokens) > 2 and toptok()[0] == '\n' : getok()
    result = (funcs, publicfuncs)
    macros = oldmacros
    macroargs = oldmacroargs
    tokens = oldtokens
    ln = oldln
    return result

def startline(toplevel=False):
    global freeregs
    oldfreeregs = freeregs[:]
    name = None
    exportstatus = None
    pushedregs = []
    if len(freeregs) < 6:
        usedregs = [r for r in allregs if r not in freeregs and r not in variables.values()]
        for r in usedregs:
            pushedregs.append(r)
            pushreg(r)
            freeregs.append(r)
    if toptok() == '@' : return doloop()
    if toptok() == '->' : return dodefer()
    if toptok() == '<':
        getok()
        exportstatus = 'extern'
        name = getok()
        if toptok() == '.' : return doimport(name)
        args = []
        while toptok() != ':' and toptok()[0] != '\n' : args.append(getok())
        match(':')
        if len(args) == 1 and isint(args[0]):
            m = int(toint(args[0]))
            args = []
            for i in range(m):
                args.append(newlabel('arg'))
        funcs[name] = args
        out(f'extern {name}')
        return '0'
    elif toptok() == '>':
        exportstatus = 'global'
        getok()
    if isid(toptok()) and not isusingid(toptok()) \
        and not (toptok() in callables and not toplevel) : name = getok()
    result = None
    assigned = False
    if name and isid(name):
        args = []
        while isalnum(toptok()):
            args.append(getok())
        if toptok() == '=' : assigned = True
        if toptok() == '~' : result = domacro(name, args)
        elif toptok() == ':' : result = dofunc(name, args, exportstatus)
        elif toptok() == '=' : result = doassign(name, args)
        elif toptok() == ':=' : result = doglobalassign(name, toplevel=toplevel)
    #print(variables)
    e = expr() if result == None else result
    for r in pushedregs[::-1]:
        if assigned and r == varloc(name):
            stk.pop()
            out('add rsp, 8')
        else : popreg(r)
    if result != None : return result
    for v in variables:
        r = varloc(v)
        if r in oldfreeregs : oldfreeregs.pop(oldfreeregs.index(r))
    freeregs = oldfreeregs
    return e

def start(filename, isfirst=True):
    global tokens
    global ln
    global funcs
    global output
    global dataoutput
    global initoutput
    global variables
    global stk
    global macros
    global globalvars
    global callables
    global defers
    global deferblocks
    global freeregs
    global bssoutput
    freeregs = allregs[::-1]
    deferblocks = []
    defers = []
    callables = {}
    globalvars = {}
    macros = {}
    variables = {}
    variables['argc_'] = getfreereg()
    variables['argv_'] = getfreereg()
    stk = []
    output = ''
    dataoutput = ''
    initoutput = ''
    bssoutput = ''
    funcs = {}
    ln = 1
    noext = filename[:filename.index('.')]
    compiled.append(filename)
    std = 'std.ot'
    prog = (f'<{std};' if filename != std else '') + open(filename).read()
    tokens = gettokens(prog + '\n\n')[::-1]

    callables, _ = getfuncs(filename)

    initexit = newlabel('initexit')
    initdone = newlabel('initdone')
    initlabel = filename.replace('.', '~')
    dataout(f'{initdone} dq 0')
    initout(f'global {initlabel}')
    initout(f'{initlabel}:')
    initout(f'mov {retreg}, {initdone}')
    initout(f'mov rbx, [{retreg}]')
    initout(f'test rbx, rbx')
    initout(f'jne {initexit}')
    initout(f'mov rbx, 1')
    initout(f'mov [{retreg}], rbx')

    if isfirst : out('global _main')
    out('_main:')
    out(f'mov rbx, 1')
    out(f'mov {retreg}, {initdone}')
    out(f'mov [{retreg}], rbx')
    while len(tokens) > 1 and toptok()[0] == '\n' : getok()
    while len(tokens) > 2:
        startline(toplevel=True)
        while len(tokens) > 1 and toptok()[0] == '\n' : getok()
    for d in defers[::-1]:
        out(f'call {d}')
    for d in deferblocks:
        tokens += d[::-1]
        startline()
    out('extern _exit')
    out('xor rdi, rdi')
    out('xor rax, rax')
    out('call _exit')
    out('ret')
    initout(initexit + ':')
    initout('ret')
    result = f'section .data\n{dataoutput}\nsection .bss\n{bssoutput}\nsection .text\n{initoutput}\n{output}'
    with open(noext + '.asm', 'w') as f:
        f.write(result)
    nasmpath = 'nasm'
    runbash(f"{nasmpath} -fmacho64 {noext}.asm")
    asmfiles.append(noext)
    with open('asmfiles.txt', 'w') as f:
        f.write('\n'.join(asmfiles))
    for i in tocompile:
        if not i in compiled:
            start(i, isfirst=False)
    return result

def runbash(bashCommand, nowarnings=True):
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)#PIPE)
    output, error = process.communicate()
    s = ''
    if output : s += str(output)
    if error : s += str(error)
    s = s.replace('\\n', '\n')
    s = '\n'.join([l for l in s.split('\n') if not 'warning' in l and len(l) > 1])
    sys.stdout.write(s)
    

prog = """
<_putchar c:
f n:                # function f takes arg n
  n ^               # match statement
    0 : 1,          # if n is 0 return 1
    _ : n * f n - 1 # default to factorial algorithm

_putchar '0' + f 3
"""

prog = """
puti_ n d:
    <_putchar c:
    _putchar n / d % 10 + '0'
    d/10 ^ 0 : _putchar 10, _ : puti_ n d/10
puti__ n d:
    n/d ^ 0 : puti__ n d/10, _ : puti_ n d
puti n : n ^ 0 : puti_ 0 9, _ : puti__ n 10000000000

f n:                # function f takes arg n
  n ^               # match statement
    0 : 1,          # if n is 0 return 1
    _ : n * f n - 1 # default to factorial algorithm

double x ~ (x * 2)

test n:
    ? n : puti 0
    ? n : 42, _ : 7

func:
    -> puti 42
    -> puti 64
    a = @[% 1 ^ 20 : len]
    puti len

fun a b:
    puti a
    puti b

read s:
    <_getchar:
    i = -1
    @ (c = _getchar) - 10 : s[++i 1] = c
    s[++i 1] = 0

readtest:
    s = @[%1^1000]
    read s
    <_puts:
    _puts s

readtest
"""

prog = """
<_puts s:
>add1 a : a + 1
str args ~ @[% 1 args]
s = str('h' 'i' '!')

<_putchar c:
a = @[1 2+2 3]
_putchar '0' + a[1]

"""

prog = r"""
<_putchar c:
f a b : a + b
fp = \f
_putchar \! fp ('0' 3)
"""
def default(filename):
    start(filename)
    runbash('gcc -c file.c')
    ofiles = ' '.join([s + '.o' for s in asmfiles] + objfiles)
    runbash(f'clang -Wl,-no_pie -o {asmfiles[0]} {ofiles}')


if __name__ == '__main__' : default(sys.argv[1])