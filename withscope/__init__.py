# This library is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see
# <http://www.gnu.org/licenses/>.


"""
Provides a scoped lexical space via the `with let(...)`
syntax. Does some really gross edits to the call frames to accomplish
this.

:author: Christopher O'Brien  <obriencj@gmail.com>
:license: LGPL v.3
"""


__all__ = ( "let", )


from inspect import currentframe
from ._frame import frame_setlocals, frame_setglobals, \
    frame_recreatecells, frame_setcells, frame_getcells


class LayeredMapping(object):
    """
    A dict-like object that will store an initial set of values, and
    will otherwise fall-through to read/write values from a baseline
    dict.
    """

    def __init__(self, baseline, defined):
        self.baseline = baseline
        self.defined = defined

    def __getitem__(self, key):
        if key in self.defined:
            return self.defined[key]
        else:
            return self.baseline[key]

    def __setitem__(self, key, value):
        #print "setting item %r in %08x to %r" % (key, id(self), value)
        if key in self.defined:
            self.defined[key] = value
        else:
            self.baseline[key] = value

    def __delitem__(self, key):
        #print "delitem %08x %r" % (id(self), key)
        if key in self.defined:
            del self.defined[key]
        else:
            del self.baseline[key]

    def __iter__(self):
        for key in self.baseline:
            if key not in self.defined:
                yield key
        for key in self.defined:
            yield key

    def __len__(self):
        return len(iter(self))

    def __contains__(self, key):
        return key in self.defined or key in self.baseline

    iterkeys = __iter__

    def keys(self):
        return list(self.iterkeys())

    def iteritems(self):
        for key, value in self.baseline.iteritems():
            if key not in self.defined:
                yield key, value
        for key, value in self.defined.iteritems():
            yield key, value

    def items(self):
        return list(self.iteritems())

    def itervalues(self):
        return (value for key,value in self.iteritems())

    def values(self):
        return list(self.itervalues())

    def __repr__(self):
        return "{%r + %r}" % (self.defined, self.baseline)

    def get(self, key, defaultval=None):
        try:
            return self[key]
        except KeyError:
            return defaultval

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        return self is other


class Scope(object):

    """
    A lexical scope, activated and revoked via the python managed
    interface methods (the `with` keyword).

    When created, specify the lexical bindings as parameters. When
    the scope is entered, those bindings will override the current
    frame's bindings for both reading and writing. When the scope
    is exited, the original bindings are restored.
    """

    def __init__(self, *args, **kwds):
        self._outer_locals = None
        self._outer_globals = None
        self._outer_cells = None
        self._inner_locals = None
        self._inner_globals = None
        self._inner_cells = None

        self.defined = dict(*args, **kwds)


    def __enter__(self):
        """
        Push our bindings, by hacking at the calling frame's locals,
        globals, and fast var cells.
        """

        #print "__enter__ for %08x" % id(self)

        caller = currentframe().f_back

        # store our existing cells, then recreate them
        self._outer_cells = frame_getcells(caller)
        if self._inner_cells is None:
            # TODO: we should only really be doing this for the cells
            # in our bindings. Need to update the recreatecells call
            # so that it accepts the defined dict and will only
            # recreate a cell bound to a defined name.
            frame_recreatecells(caller)
            self._inner_cells = frame_getcells(caller)
        else:
            frame_setcells(caller, self._inner_cells)

        # store the existing locals, then create a layer atop that and
        # swap into place.
        self._outer_locals = caller.f_locals
        if self._inner_locals is None:
            layered = LayeredMapping(self._outer_locals, self.defined)
            self._inner_locals = layered
        else:
            self._inner_locals.baseline = self._outer_locals
        frame_setlocals(caller, self._inner_locals)

        self._outer_globals = caller.f_globals

        # can't use a LayeredDict for globals -- it only accepts pure
        # dict instances apparently. This is fine, since any
        # assignment would actually cause a write to locals rather
        # than globals, we only need globals in place to find
        # variables not already defined via normal syntax.
        self._inner_globals = dict(self._outer_globals)

        # todo: create a smaller defined set, of ONLY those defined
        # names which aren't in the frame's locals already -- we're
        # going to pretend they are global values for the duration of
        # the scope
        self._inner_globals.update(self.defined)

        frame_setglobals(caller, self._inner_globals)

        return self


    def __exit__(self, exc_type, _exc_val, _exc_tb):
        """
        Pop our bindings
        """

        #print "__exit__ for %08x" % id(self)

        caller = currentframe().f_back
        caller.f_locals # this triggers copying the fast locals into
                        # the current locals dict, before we reset
                        # them, allowing outer scope references to be
                        # preserved and not incorrectly rewritten

        frame_setcells(caller, self._outer_cells)
        frame_setlocals(caller, self._outer_locals)
        frame_setglobals(caller, self._outer_globals)

        self._outer_cells = None
        self._outer_locals = None
        self._outer_globals = None

        return exc_type is None


"""
provide a happy little binding for the Scope class
"""
let = Scope


#
# The end.
