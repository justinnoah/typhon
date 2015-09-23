from typhon.atoms import getAtom
from typhon.autohelp import autohelp
from typhon.objects.auditors import deepFrozenStamp
from typhon.objects.collections import ConstList
from typhon.objects.data import StrObject
from typhon.objects.ejectors import throw
from typhon.objects.root import Object, runnable


RUN_2 = getAtom(u"run", 2)


@autohelp
class SealedException(Object):
    """
    An exception.

    Sealed within this object are the details of an exceptional occurrence.
    """

    def __init__(self, value, trail):
        self.value = value
        self.trail = trail

    def toString(self):
        return u"<sealed exception>"


@runnable(RUN_2, _stamps=[deepFrozenStamp])
def unsealException(args):
    """
    Unseal a specimen.
    """

    specimen = args[0]
    ej = args[1]

    if isinstance(specimen, SealedException):
        trail = ConstList([StrObject(s) for s in specimen.trail])
        return ConstList([specimen.value, trail])
    throw(ej, StrObject(u"Cannot unseal non-thrown object"))
