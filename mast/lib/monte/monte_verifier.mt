import "unittest" =~ [=> unittest]
exports (findUndefinedNames, findUnusedNames)

def Ast :DeepFrozen := ::"m``".getAstBuilder().getAstGuard()
def Noun :DeepFrozen := ::"m``".getAstBuilder().getNounGuard()

def findUndefinedNames(expr, outers) as DeepFrozen:
    def outerNames := [for `&&@name` in (outers.getKeys()) name].asSet()
    def ss := expr.getStaticScope()
    def namesUsed := ss.namesUsed().asSet()
    def offenders := namesUsed &! outerNames
    if (offenders.size() == 0):
        # all good, only names closed over are outers
        return []
    def results := [].diverge()
    def stack := [].diverge()
    def descendInto(item):
        for a in (item._uncall()[2]):
            switch (a):
                match _ :Ast:
                    stack.push(a)
                match _ :List[Ast]:
                    stack.extend(a)
                match _:
                    null
    descendInto(expr)
    while (stack.size() > 0):
        def item := stack.pop()
        def names := item.getStaticScope().namesUsed().asSet()
        if ((offenders & names).size() > 0):
            if (["NounExpr", "SlotExpr", "BindingExpr"].contains(item.getNodeName())):
                results.push(item)
            descendInto(item)
    return results

def leaves :Set[Str] := [
    "BindingExpr",
    "LiteralExpr",
    "NounExpr",
    "SlotExpr",
    "QuasiText",
    "IgnorePattern",
].asSet()

def flattenList(l :List[List]) :List as DeepFrozen:
    var rv := []
    for x in (l) { rv += x }
    traceln(`flattened $l to $rv`)
    return rv

def optional(l :NullOk[List]) :List as DeepFrozen:
    return if (l == null) { [] } else { l }

def filterNouns(l :List[Noun], s :Set[Str]) :List[Noun] as DeepFrozen:
    traceln(`filtering $l with $s`)
    return [for noun in (l) ? (!s.contains(noun.getName())) noun]

def usedSet(node) :Set[Str] as DeepFrozen:
    return node.getStaticScope().getNamesRead()

def findUnusedNames(expr) :List[Noun] as DeepFrozen:
    "
    Find names in `expr` which are not used.

    To indicate that a name is intentionally unused, simply prefix it with
    '_'.
    "

    def unusedNameFinder(node, maker, args, span) :List[Noun]:
        def rv := switch (node.getNodeName()) {
            # Modules
            match =="Module" {
                def [importsList, exportsList, body] := args
                def incoming := flattenList([for [_, patt] in (importsList) patt])
                def l := filterNouns(incoming, usedSet(node.getBody()))
                def s := {
                    var rv := [].asSet()
                    for ex in (node.getExports()) { rv |= usedSet(ex) }
                    rv
                }
                l + filterNouns(body, s)
            }
            # Sequences.
            match =="SeqExpr" {
                var rv := []
                def exprs := node.getExprs()
                for i => expr in (args[0]) {
                    traceln(`iteration $i $expr ${exprs[i]}`)
                    rv += expr
                    def namesRead := usedSet(exprs[i])
                    rv := filterNouns(rv, namesRead)
                    traceln(`rv $rv`)
                }
                rv
            }
            # Full exprs.
            match =="AssignExpr" { flattenList(args) }
            match =="AugAssignExpr" {
                def [_, lvalue, rvalue] := args
                lvalue + rvalue
            }
            match =="BinaryExpr" {
                def [left, _, right] := args
                left + right
            }
            match =="CatchExpr" {
                def [body, patt, catcher] := args
                body + filterNouns(patt + catcher, usedSet(node.getCatcher()))
            }
            match =="CurryExpr" { args[0] }
            match =="DefExpr" {
                def [pattern, exit_, rhs] := args
                pattern + optional(exit_) + rhs
            }
            match =="EscapeExpr" {
                def [ejPatt, ejBody, catchPatt, catchBody] := args
                def ej := filterNouns(ejPatt + ejBody,
                                      usedSet(node.getBody()))
                if (catchBody != null) {
                    def c := filterNouns(catchPatt + catchBody,
                                         usedSet(node.getCatchBody()))
                    ej + c
                } else {
                    ej
                }
            }
            match =="ExitExpr" { optional(args[1]) }
            match =="ForExpr" {
                def [iterable, key, value, body, catchPatt, catchBody] := args
                def l := filterNouns(iterable + optional(key) + value + body,
                                     usedSet(node.getBody()))
                def c := if (catchBody != null) {
                    filterNouns(catchPatt + catchBody,
                                usedSet(node.getCatchBody()))
                } else { [] }
                l + c
            }
            match =="FunCallExpr" {
                def [receiver, arguments, namedArgs] := args
                receiver + flattenList(arguments) + flattenList(namedArgs)
            }
            match =="FunctionExpr" {
                def [patts, body] := args
                filterNouns(flattenList(patts) + body,
                            usedSet(node.getBody()))
            }
            match =="GetExpr" {
                def [receiver, indices] := args
                receiver + flattenList(indices)
            }
            match =="IfExpr" {
                def [test, consq, alt] := args
                def l := test + consq + optional(alt)
                var namesRead := usedSet(node.getThen())
                if (alt != null) { namesRead |= usedSet(node.getElse()) }
                filterNouns(l, namesRead)
            }
            match n ? (["ListExpr", "MapExpr"].contains(n)) {
                flattenList(args[0])
            }
            match =="MapExprExport" { args[0] }
            match =="MatchBindExpr" { flattenList(args) }
            match =="MethodCallExpr" {
                def [receiver, _, arguments, namedArgs] := args
                receiver + flattenList(arguments) + flattenList(namedArgs)
            }
            match =="PrefixExpr" { args[1] }
            match n ? (["QuasiExprHole", "QuasiPatternHole"].contains(n)) {
                args[0]
            }
            match =="QuasiParserExpr" {
                def [_, quasis] := args
                flattenList(quasis)
            }
            match =="RangeExpr" {
                def [left, _, right] := args
                left + right
            }
            match =="SameExpr" {
                def [left, right, _] := args
                left + right
            }
            match =="TryExpr" { flattenList(args) }
            match =="VerbAssignExpr" {
                def [_, lvalue, rvalues] := args
                lvalue + flattenList(rvalues)
            }
            match =="WhenExpr" {
                def [arguments, body, catchers, finallyBlock] := args
                def l := filterNouns(flattenList(arguments) + body,
                                     usedSet(node.getBody()))
                l + flattenList(catchers) + optional(finallyBlock)
            }
            # Named arguments.
            match =="NamedArg" { flattenList(args) }
            match =="NamedArgExport" { args[0] }
            match =="NamedParamImport" { args[0] }
            # Script pieces.
            match =="FunctionScript" {
                def [patts, namedPatts, guard, body] := args
                def l := flattenList(patts) + flattenList(namedPatts) + body
                optional(guard) + filterNouns(l, usedSet(node.getBody()))
            }
            match =="ObjectExpr" {
                def [_, name, asExpr, auditors, script] := args
                name + optional(asExpr) + flattenList(auditors) + script
            }
            match =="Script" {
                def [extend, methods, matchers] := args
                optional(extend) + flattenList(methods) + flattenList(matchers)
            }
            match =="To" {
                def [_, _, patts, namedPatts, guard, body] := args
                def l := (flattenList(patts) + flattenList(namedPatts) +
                          optional(guard))
                def namesRead := usedSet(node.getBody())
                filterNouns(l, namesRead)
            }
            # Patterns.
            match n ? (["FinalPattern", "SlotPattern",
                        "VarPattern"].contains(n)) {
                def noun := node.getNoun()
                [noun] + optional(args[1])
            }
            match n ? (["ListPattern", "MapPattern"].contains(n)) {
                def [patts, tail] := args
                def ps := flattenList(patts)
                ps + optional(tail)
            }
            match =="MapPatternImport" {
                def [patt, default] := args
                patt + optional(default)
            }
            match =="ViaPattern" { flattenList(args) }
            # Empty leaves which can't contain anything interesting.
            match leaf ? (leaves.contains(leaf)) { [] }
            match nodeName { throw(`Unsupported node $nodeName $node`) }
        }
        traceln(`nodeName ${node.getNodeName()} rv $rv`)
        return rv
    return expr.transform(unusedNameFinder)

def testUnusedDef(assert):
    assert.equal(m`def x := 42; "asdf"`.transform(findUnusedNames).size(), 1)

unittest([
    testUnusedDef,
])
