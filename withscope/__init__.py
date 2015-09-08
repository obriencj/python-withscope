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

from ._frame import frame_clone, frame_swap_cells, \
    frame_set_f_lasti, frame_set_f_back, \
    frame_set_f_locals, frame_set_f_globals, \
    frame_clear_f_executing


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


class ScopeInUse(Exception):
    """
    Raised when an already in-use scope is called to activate itself
    again.
    """
    pass


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
        self.defined = dict(*args, **kwds)

        # create cells for all our values. They may or may not all get
        # used, depending on the variety of frames we get called from
        # within.
        self._cells = dict((key, _cell(val)) for key,val
                           in self.defined.iteritems())

        # our original parent frame upon entry. Also used as a
        # sentinel to determine if we're already in-use as a lexical
        # scope.
        self._outer_caller = None

        # our duplicated parent frame, representing our scope
        self._inner_caller = None


    def alias(self):
        """
        Create an alias scope that can be entered while the original is
        still active. References the same defined values and cells, but
        is otherwise a separate instance.
        """

        dup = self.__new__(type(self))
        dup.defined = self.defined
        dup._cells = self._cells
        dup._outer_caller = None
        dup._inner_caller = None
        return dup


    def __enter__(self):
        """
        Push our bindings, by hacking at the calling frame's locals,
        globals, and fast var cells.
        """

        #print "__enter__ for %08x" % id(self)

        if self._outer_caller is not None:
            raise ScopeInUse(self)

        assert(self._outer_caller is None)
        assert(self._inner_caller is None)

        current = currentframe()

        # we'll duplicate our calling frame, and then modify the
        # current frame to return to our specialty duplicate
        # instead. We'll perform similar hackery in the __exit__
        # method so that when the scope ends, we properly return to
        # the original caller and execution can continue as planned.
        caller = current.f_back
        dup_caller = frame_duplicate(caller, inner_globals, inner_locals)

        self._outer_caller = caller
        self._inner_caller = dup_caller

        # search through the cells in our duplicate frame and if they
        # are named after any in our cell set, swap them. Note we'll
        # be discarding the dup frame at the end of scope, so no
        # worries.
        frame_swap_cells(dup_caller, self._cells)

        # store the existing locals, then create a layer atop that and
        # swap into place.
        outer_locals = caller.f_locals
        inner_locals = LayeredMapping(self._outer_locals, self.defined)
        frame_set_f_locals(caller, self._inner_locals)

        # can't use a LayeredDict for globals -- it only accepts pure
        # dict instances apparently. This is fine, since any
        # assignment would actually cause a write to locals rather
        # than globals, we only need globals in place to find
        # variables not already defined via normal syntax.
        inner_globals = dict(caller.f_globals)
        inner_globals.update(self.defined)
        frame_set_f_globals(dup_caller, inner_globals)
        # TODO: create a smaller subset of defined using ONLY those
        # keys which aren't in the frame's locals already -- we're
        # going to pretend they are global values for the duration of
        # the scope

        # we will now return to our duplicated caller
        frame_set_f_back(current, dup_caller)

        return self


    def __exit__(self, exc_type, _exc_val, _exc_tb):
        """
        Pop our bindings
        """

        #print "__exit__ for %08x" % id(self)

        current = currentframe()
        assert(self._inner_caller is current.f_back)

        # f_locals is a dynamic attribute. This triggers copying the
        # fast locals into the current locals dict, before we reset
        # them, allowing outer scope references to be preserved and
        # not incorrectly rewritten
        self._inner_caller.f_locals

        code_index = self._inner_caller.f_lasti
        frame_set_f_lasti(self._outer_caller, code_index)

        # we will now be able to return execution to our original
        # caller frame, captured during __enter__
        frame_set_f_back(current, self._outer_caller)

        # now that f_back is set to the original frame, the dup frame
        # can be marked as no longer in service, and cleaned up.
        frame_clear_f_executing(self._inner_caller)
        self._inner_caller.clear()

        self._inner_caller = None
        self._outer_caller = None

        return exc_type is None


"""
provide a happy little binding for the Scope class
"""
let = Scope


#
# The end.
