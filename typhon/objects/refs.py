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

import weakref

from typhon.atoms import getAtom
from typhon.errors import Refused, userError
from typhon.objects.collections import ConstList
from typhon.objects.constants import NullObject, unwrapBool, wrapBool
from typhon.objects.data import StrObject
from typhon.objects.root import Object


class RefState(object):
    pass

BROKEN, EVENTUAL, NEAR = RefState(), RefState(), RefState()

BROKEN_1 = getAtom(u"broken", 1)
ISBROKEN_1 = getAtom(u"isBroken", 1)
ISRESOLVED_1 = getAtom(u"isResolved", 1)
PROMISE_0 = getAtom(u"promise", 0)
RESOLVE_1 = getAtom(u"resolve", 1)
RESOLVE_2 = getAtom(u"resolve", 2)
RUN_1 = getAtom(u"run", 1)
STATE_1 = getAtom(u"state", 1)
WHENBROKEN_2 = getAtom(u"whenBroken", 2)
WHENRESOLVED_2 = getAtom(u"whenResolved", 2)
_PRINTON_1 = getAtom(u"_printOn", 1)
_WHENBROKEN_1 = getAtom(u"_whenBroken", 1)
_WHENMORERESOLVED_1 = getAtom(u"_whenMoreResolved", 1)


def makePromise(vat):
    buf = MessageBuffer(vat)
    sref = SwitchableRef(BufferingRef(buf, vat), vat)
    return sref, LocalResolver(vat, sref, buf)


def _toRef(o, vat):
    if isinstance(o, Promise):
        return o
    return NearRef(o, vat)


def resolution(o):
    if isinstance(o, Promise):
        return o.resolution()
    return o


def isResolved(o):
    if isinstance(o, Promise):
        return o.isResolved()
    else:
        return True


class RefOps(Object):
    """
    Public functions for ref manipulation. Exposed in safescope as 'Ref'.
    """

    def __init__(self, vat):
        self._vat = vat

    def toString(self):
        return u"<Ref>"

    def recv(self, atom, args):
        if atom is BROKEN_1:
            return self.broken(args[0].toString())

        if atom is ISBROKEN_1:
            return wrapBool(self.isBroken(args[0]))

        if atom is ISRESOLVED_1:
            return wrapBool(isResolved(args[0]))

        if atom is PROMISE_0:
            return self.promise()

        # Inlined for name clash reasons.
        if atom is STATE_1:
            o = args[0]
            if isinstance(o, Promise):
                s = o.state()
            else:
                s = NEAR

            if s is EVENTUAL:
                return StrObject(u"EVENTUAL")
            if s is NEAR:
                return StrObject(u"NEAR")
            if s is BROKEN:
                return StrObject(u"BROKEN")
            return StrObject(u"UNKNOWN")

        if atom is WHENBROKEN_2:
            return self.whenBroken(args[0], args[1])

        if atom is WHENRESOLVED_2:
            return self.whenResolved(args[0], args[1])

        raise Refused(self, atom, args)

    def promise(self):
        p, r = makePromise(self._vat)
        return ConstList([p, r])

    def broken(self, problem):
        return UnconnectedRef(problem, self._vat)

    def optBroken(self, optProblem):
        if optProblem is NullObject:
            return NullObject
        else:
            return self.broken(optProblem.toString())

    def isNear(self, ref):
        if isinstance(ref, Promise):
            return ref.state() is NEAR
        else:
            return True

    def isEventual(self, ref):
        if isinstance(ref, Promise):
            return ref.state() is EVENTUAL
        else:
            return False

    def isBroken(self, ref):
        if isinstance(ref, Promise):
            return ref.state() is BROKEN
        else:
            return False

    def optProblem(self, ref):
        if isinstance(ref, Promise):
            return ref.problem
        return NullObject

#    def fulfillment(self, ref):
#        ref = self.resolution(ref)
#        p = self.optProblem(ref)
#        if self.isResolved(ref):
#            if p is NullObject:
#                return ref
#            else:
#                raise p
#        else:
#            raise RuntimeError("Not resolved: %r" % (ref,))

    def isFar(self, ref):
        return self.isEventual(ref) and self.isResolved(ref)

    def whenResolved(self, o, callback):
        p, r = makePromise(self._vat)
        self._vat.sendOnly(o, u"_whenMoreResolved",
                [WhenResolvedReactor(callback, o, r, self._vat)])
        return p

    def whenResolvedOnly(self, o, callback):
        self._vat.sendOnly(o, u"_whenMoreResolved",
                [WhenResolvedReactor(callback, o, None, self._vat)])
        return NullObject

    def whenBroken(self, o, callback):
        p, r = makePromise(self._vat)
        self._vat.sendOnly(o, u"_whenMoreResolved",
                [WhenBrokenReactor(callback, o, r, self._vat)])
        return p

    def whenBrokenOnly(self, o, callback):
        return self._vat.sendOnly(o, u"_whenMoreResolved",
                [WhenBrokenReactor(callback, o, None, self._vat)])
        return NullObject

    def isDeepFrozen(self, o):
        # XXX
        return False

    def isSelfless(self, o):
        # XXX
        return False

    def isSelfish(self, o):
        return self.isNear(o) and not self.isSelfless(o)


class WhenBrokenReactor(Object):

    def __init__(self, callback, ref, resolver, vat):
        self._cb = callback
        self._ref = ref
        self._resolver = resolver
        self._vat = vat

    def toString(self):
        return u"<whenBrokenReactor>"

    def recv(self, atom, args):
        if atom is RUN_1:
            if not isinstance(self._ref, Promise):
                return NullObject

            if self._ref.state() is EVENTUAL:
                self._vat.sendOnly(self._ref, u"_whenMoreResolved", [self])
            elif self._ref.state() is BROKEN:
                try:
                    outcome = self._cb.call(u"run", [self._ref])
                except Exception, e:
                    # XXX reify and raise?
                    # outcome = e
                    raise

                if self._resolver is not None:
                    self._resolver.resolve(outcome)

            return NullObject
        raise Refused(self, atom, args)


class WhenResolvedReactor(Object):

    done = False

    def __init__(self, callback, ref, resolver, vat):
        self._cb = callback
        self._ref = _toRef(ref, vat)
        self._resolver = resolver
        self._vat = vat

    def toString(self):
        return u"<whenResolvedReactor>"

    def recv(self, atom, args):
        if atom is RUN_1:
            if self.done:
                return NullObject

            if self._ref.isResolved():
                try:
                    outcome = self._cb.call(u"run", [self._ref])
                except Exception, e:
                    # XXX reify the exception and raise it in Monte
                    raise
                    # outcome = e

                if self._resolver is not None:
                    self._resolver.resolve(outcome)

                self.done = True
            else:
                self._vat.sendOnly(self._ref, u"_whenMoreResolved", [self])

            return NullObject
        raise Refused(self, atom, args)


class LocalResolver(Object):

    def __init__(self, vat, ref, buf):
        self._vat = vat
        self._ref = ref
        self._buf = buf

    def toString(self):
        if self._ref is None:
            return u"<closed resolver>"
        else:
            return u"<resolver>"

    def recv(self, atom, args):
        if atom is RESOLVE_1:
            return wrapBool(self.resolve(args[0]))

        if atom is RESOLVE_2:
            return wrapBool(self.resolve(args[0], unwrapBool(args[1])))

        raise Refused(self, atom, args)

    def resolve(self, target, strict=True):
        if self._ref is None:
            if strict:
                raise userError(u"Already resolved")
            return False
        else:
            self._ref.setTarget(_toRef(target, self._vat))
            self._ref.commit()
            self._buf.deliverAll(target)

            self._ref = None
            self._buf = None
            return True

    def resolveRace(self, target):
        return self.resolve(target, False)

    def smash(self, problem):
        return self.resolve(UnconnectedRef(problem, self._vat), False)

    def isDone(self):
        return wrapBool(self._ref is None)


class MessageBuffer(object):

    def __init__(self, vat):
        self._vat = vat
        self._buf = []

    def enqueue(self, resolver, atom, args):
        self._buf.append((resolver, atom, args))

    def deliverAll(self, target):
        #XXX record sending-context information for causality tracing
        targRef = _toRef(target, self._vat)
        for resolver, atom, args in self._buf:
            if resolver is None:
                targRef.sendAllOnly(atom, args)
            else:
                result = targRef.sendAll(atom, args)
                resolver.resolve(result)
        rv = len(self._buf)
        self._buf = []
        return rv


class Promise(Object):
    """
    A promised reference.

    All methods on this class are helpers; this class cannot be instantiated
    directly.
    """

    # Monte core.

    def recv(self, atom, args):
        if atom is _PRINTON_1:
            out = args[0]
            return out.call(u"print", [StrObject(self.toString())])

        if atom is _WHENMORERESOLVED_1:
            return self._whenMoreResolved(args[0])

        return self.callAll(atom, args)

    def _whenMoreResolved(self, callback):
        # Welcome to _whenMoreResolved.
        # This method's implementation, in Monte, should be:
        # to _whenMoreResolved(callback): callback<-(self)
        self.vat.sendOnly(callback, u"run", [self])
        return NullObject

    # Synchronous calls.

    # Eventual sends.

    def send(self, verb, args):
        # Resolution is done by the vat here; we don't get to access the
        # resolver ourselves.
        return self.sendAll(getAtom(verb, len(args)), args)

    def sendOnly(self, verb, args):
        self.sendAllOnly(getAtom(verb, len(args)), args)
        return NullObject

    # Promise API.

    def resolutionRef(self):
        return self

    def resolution(self):
        result = self.resolutionRef()
        if self is result:
            return result
        else:
            return result.resolution()

    def state(self):
        if self.optProblem() is not NullObject:
             return BROKEN
        target = self.resolutionRef()
        if self is target:
            return EVENTUAL
        else:
            return target.state()


class SwitchableRef(Promise):
    """
    Starts out pointing to one promise and switches to another later.
    """

    isSwitchable = True

    def __init__(self, target, vat):
        self._target = target
        self.vat = vat

    def toString(self):
        if self.isSwitchable:
            return u"<switchable promise>"
        else:
            self.resolutionRef()
            return self._target.toString()

    def callAll(self, atom, args):
        if self.isSwitchable:
            raise userError(u"not synchronously callable (%s)" %
                    atom.repr().decode("utf-8"))
        else:
            self.resolutionRef()
            return self._target.callAll(atom, args)

    def sendAll(self, atom, args):
        self.resolutionRef()
        return self._target.sendAll(atom, args)

    def sendAllOnly(self, atom, args):
        self.resolutionRef()
        return self._target.sendAllOnly(atom, args)

    def optProblem(self):
        if self.isSwitchable:
            return NullObject
        else:
            self.resolutionRef()
            return self._target.optProblem()

    def resolutionRef(self):
        self._target = self._target.resolutionRef()
        if self.isSwitchable:
            return self
        else:
            return self._target

    def state(self):
        if self.isSwitchable:
            return EVENTUAL
        else:
            self.resolutionRef()
            return self._target.state()

    def isResolved(self):
        if self.isSwitchable:
            return False
        else:
            self.resolutionRef()
            return self._target.isResolved()

    def setTarget(self, newTarget):
        if self.isSwitchable:
           self._target = newTarget.resolutionRef()
           if self is self._target:
               raise userError(u"Ref loop")
        else:
            raise userError(u"No longer switchable")

    def commit(self):
        if not self.isSwitchable:
            return
        newTarget = self._target.resolutionRef()
        self._target = None
        self.isSwitchable = False
        newTarget = newTarget.resolutionRef()
        if newTarget is None:
            raise userError(u"Ref loop")
        else:
            self._target = newTarget


class BufferingRef(Promise):

    def __init__(self, buf, vat):
        # Note to self: Weakref.
        self._buf = weakref.ref(buf)
        self.vat = buf._vat

    def toString(self):
        return u"<bufferingRef>"

    def callAll(self, atom, args):
        raise userError(u"not synchronously callable (%s)" %
                atom.repr().decode("utf-8"))

    def sendAll(self, atom, args):
        optMsgs = self._buf()
        if optMsgs is None:
            # XXX what does it mean for us to have no more buffer?
            return self
        else:
            p, r = makePromise(self.vat)
            optMsgs.enqueue(r, atom, args)
            return p

    def sendAllOnly(self, atom, args):
        optMsgs = self._buf()
        if optMsgs is not None:
            optMsgs.enqueue(None, atom, args)
        return NullObject

    def optProblem(self):
        return NullObject

    def resolutionRef(self):
        return self

    def state(self):
        return EVENTUAL

    def isResolved(self):
        return False

    def commit(self):
        pass


class NearRef(Promise):

    def __init__(self, target, vat):
        self.target = target
        self.vat = vat

    def toString(self):
        return u"<nearref: %s>" % self.target.toString()

    def callAll(self, atom, args):
        return self.target.call(atom.verb, args)

    def sendAll(self, atom, args):
        return self.vat.send(self.target, atom.verb, args)

    def sendAllOnly(self, atom, args):
        return self.vat.sendOnly(self.target, atom.verb, args)

    def optProblem(self):
        return NullObject

    def state(self):
        return NEAR

    def resolution(self):
        return self.target

    def resolutionRef(self):
        return self

    def isResolved(self):
        return True

    def commit(self):
        pass


class UnconnectedRef(Promise):

    def __init__(self, problem, vat):
        assert isinstance(problem, unicode)
        self._problem = problem
        self._vat = vat

    def toString(self):
        return u"<ref broken by %s>" % (self._problem,)

    def callAll(self, atom, args):
        self._doBreakage(atom, args)
        raise userError(self._problem)

    def sendAll(self, atom, args):
        self._doBreakage(atom, args)
        return self

    def sendAllOnly(self, atom, args):
        return self._doBreakage(atom, args)

    def state(self):
        return BROKEN

    def resolutionRef(self):
        return self

    def _doBreakage(self, atom, args):
        if atom in (_WHENMORERESOLVED_1, _WHENBROKEN_1):
            return self._vat.sendOnly(args[0], u"run", [self])

    def isResolved(self):
        return True

    def commit(self):
        pass