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


__all__ = ("let", "Scope", "ScopeException", "ScopeInUse", "ScopeMismatch")


from inspect import currentframe
from ._frame import cell_from_value, frame_swap_fast_cells, \
    frame_set_f_locals, frame_set_f_globals


class ScopeException(Exception):
    """
    Base class for the ScopeInUse and ScopeMismatch errors.
    """

    pass


class ScopeInUse(ScopeException):
    """
    raised when a Scope is entered while already
    active. `Scope.alias()` can be used to create a duplicate Scope
    which can be re-used while the original was stil in use
    """

    pass


class ScopeMismatch(ScopeException):
    """
    raised when a Scope is exited and the parent frame does not match
    with the parent frame when entered. In general this is only
    possible if someone were to manually call the __enter__/__exit__
    method of the Scope, incorrectly.
    """

    pass


class LayeredMapping(object):
    """
    A dict-like object that will store an initial set of values, and
    will otherwise fall-through to read/write values from a baseline
    dict.
    """

    def __init__(self, baseline, defined):
        self.baseline = baseline
        self.defined = defined
        self._delkeys = set()


    def __getitem__(self, key):
        # no fall-through if it was originally defined but deleted
        if key in self.defined or key in self._delkeys:
            return self.defined[key]
        else:
            return self.baseline[key]


    def __setitem__(self, key, value):
        #print "setting item %r in %08x to %r" % (key, id(self), value)
        if key in self.defined:
            self.defined[key] = value
        elif key in self._delkeys:
            self._delkeys.remove(key)
            self.defined[key] = value
        else:
            self.baseline[key] = value


    def __delitem__(self, key):
        #print "delitem %08x %r" % (id(self), key)
        if key in self.defined or key in self._delkeys:
            self._delkeys.add(key)
            del self.defined[key]
        else:
            del self.baseline[key]


    def __iter__(self):
        for key in self.baseline:
            if key not in self.defined and key not in self._delkeys:
                yield key
        for key in self.defined:
            yield key


    def __len__(self):
        count = 0
        for count, _val in enumerate(iter(self), 1):
            pass
        return count


    def __contains__(self, key):
        return (key in self.defined or
                (key in self.baseline and
                 key not in self._delkeys))


    iterkeys = __iter__


    def keys(self):
        return list(self.iterkeys())


    def iteritems(self):
        for key, value in self.baseline.iteritems():
            if key not in self.defined and key not in self._delkeys:
                yield key, value
        for key, value in self.defined.iteritems():
            yield key, value


    def items(self):
        return list(self.iteritems())


    def itervalues(self):
        return (value for key, value in self.iteritems())


    def values(self):
        return list(self.itervalues())


    def __repr__(self):
        return "{%r + %r}" % (self.baseline, self.defined)


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

    Example:

    >>> from withscope import let
    >>> a = "taco"
    >>> with let(a="pizza", b="beer"):
    ...     print "%s and %s" % (a, b)
    ...
    pizza and beer
    >>> print a
    taco
    >>> print b
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    NameError: name 'b' is not defined
    """

    def __init__(self, *args, **kwds):
        self._defined = dict(*args, **kwds)
        self._cells = dict((key, cell_from_value(val)) for
                           key, val in self._defined.iteritems())

        # this is the state we gather at __enter__ and need to restore
        # at __exit__
        self._outer_frame = None
        self._outer_locals = None
        self._outer_globals = None
        self._outer_cells = None
        self._inner_locals = None
        self._inner_globals = None

        # optional Scope instance that we may be an alias of.  TODO:
        # on __exit__ we should propagate our edits to self._defined
        # to the _alias_parent such that if it is in_use, its frame is
        # updated.
        self._alias_parent = None


    def alias(self):
        """
        Create an alias scope that can be entered while the original is
        still active. References the same defined values and cells, but
        is otherwise a separate instance.
        """

        dup = self.__new__(type(self))
        dup._defined = self._defined
        dup._cells = self._cells

        dup._outer_frame = None
        dup._outer_locals = None
        dup._outer_globals = None
        dup._outer_cells = None
        dup._inner_locals = None
        dup._inner_globals = None

        dup._alias_parent = self

        return dup


    def scope_locals(self):
        """
        Get a representation of the locals specific to this
        scope. Modifying these values while the scope is in-use is not
        recommended, and will have difficult-to-explain results
        depending on the particulars of the named value being changed.
        """

        if self._outer_frame:
            # if we're in-use, refresh our locals dict
            self._outer_frame.f_locals

        return self._defined


    def in_use(self):
        """
        Boolean noting whether this scope is currently in-use
        """
        return self._outer_frame is not None


    def _reapply_frame(self):
        if self._outer_frame:
            self._revert_frame(False)
            self._apply_frame()


    def _apply_frame(self):
        """
        Apply our bindings to our frame
        """

        frame = self._outer_frame
        assert(frame is not None)

        defined = self._defined

        self._outer_locals = frame.f_locals
        self._outer_globals = frame.f_globals

        # make sure to do this after observing f_locals, since
        # fetching f_locals has the side-effect of mucking with cell
        # values.
        self._outer_cells = frame_swap_fast_cells(frame, self._cells)

        # create a layered view that combines our defined variables
        # on top of the previously existing locals
        inner_locals = LayeredMapping(self._outer_locals, defined)
        frame_set_f_locals(frame, inner_locals)
        self._inner_locals = inner_locals

        # we'll duplicate globals, and inject any "read-only" values
        # from defined into it. We know something is only going to be
        # read when it's not used in co_varnames.
        inner_globals = None
        varnames = frame.f_code.co_varnames
        if varnames:
            for key, val in defined.iteritems():
                if key not in varnames:
                    if inner_globals is None:
                        inner_globals = dict(self._outer_globals)
                    inner_globals[key] = val

        # only bother overriding globals if we needed to do so.
        if inner_globals:
            frame_set_f_globals(frame, inner_globals)
            self._inner_globals = inner_globals


    def _revert_frame(self, merge=True):
        """
        Revert our frame and ensure our defined storage matches what was
        in the frame's vars.
        """

        frame = self._outer_frame
        assert(frame is not None)

        if merge:
            # this triggers copying the fast locals into the current
            # locals dict, before we reset them, allowing outer scope
            # references to be preserved and not incorrectly rewritten
            _l = frame.f_locals

        # put our original cells back
        frame_swap_fast_cells(frame, self._outer_cells)

        # put our locals back, which has the side-effect of syncing
        # the cell values
        frame_set_f_locals(frame, self._outer_locals)

        # only bother resetting globals if it were overridden
        if self._inner_globals:
            frame_set_f_globals(frame, self._outer_globals)

        self._outer_cells = None
        self._outer_locals = None
        self._outer_globals = None

        self._inner_locals = None
        self._inner_globals = None


    def __enter__(self):
        """
        Push our bindings, by hacking at the calling frame's locals,
        globals, and fast var cells. We are considered in-use until
        __exit__ is called.
        """

        #print "__enter__ for %08x" % id(self)

        if self._outer_frame:
            raise ScopeInUse()

        caller = currentframe().f_back
        self._outer_frame = caller

        # ensure our defined values are up-to-date from the parent
        # scope, if we are an alias
        parent = self._alias_parent
        if parent:
            parent.scope_locals()

        self._apply_frame()

        return self


    def __exit__(self, exc_type, _exc_val, _exc_tb):
        """
        Pop our bindings, and we are no longer considered to be
        in-use. Also syncs the scope variables to any parent aliases.
        """

        #print "__exit__ for %08x" % id(self)

        caller = currentframe().f_back
        if self._outer_frame is not caller:
            raise ScopeMismatch()

        # if we are an alias, we have to first let the parent
        # get a sync'd copy of its variables from the frame. We
        # can force this via asking it to calculate scope_locals
        parent = self._alias_parent
        if parent:
            _l = parent.scope_locals()

        self._revert_frame()
        self._outer_frame = None

        # if we are an alias, we have to now tell the parent
        # that we've updated the shared defined dict, and have it
        # apply those variables into its frame
        if parent:
            parent._reapply_frame()

        return exc_type is None


# provide a happy little binding for the Scope class
let = Scope


#
# The end.
