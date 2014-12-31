# Copyright (C) 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from rpython.rlib.listsort import TimSort

from typhon.errors import UserException
from typhon.load import load
from typhon.nodes import Sequence, evaluate
from typhon.objects.constants import NullObject
from typhon.optimizer import optimize
from typhon.scope import Scope


def obtainModule(path, inputScope, recorder):
    with recorder.context("Deserialization"):
        term = Sequence(load(open(path, "rb").read())[:])
    # First pass: Unshadow.
    with recorder.context("Scope analysis"):
        TimSort(inputScope).sort()
        scope = Scope(inputScope)
        term = term.rewriteScope(scope)
    with recorder.context("Optimization"):
        term = optimize(term)
    # Second pass: Collect the initial scope size.
    with recorder.context("Scope analysis"):
        scope = Scope(inputScope)
        term = term.rewriteScope(scope)

    print "Optimized node:"
    print term.repr()
    term.frameSize = scope.size()
    return term


def evaluateWithTraces(term, env):
    try:
        return evaluate(term, env)
    except UserException as ue:
        print "Caught exception:", ue.formatError()
        return None


def evaluateTerms(terms, env):
    result = NullObject
    for term in terms:
        result = evaluateWithTraces(term, env.new(term.frameSize))
        if result is None:
            print "Evaluation returned None!"
        else:
            print result.toQuote()
    return result