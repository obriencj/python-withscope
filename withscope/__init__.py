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


from functools import partial
from inspect import currentframe
from operator import is_

from ._frame import (cell_get_value, cell_set_value,
                     cell_from_value, frame_set_f_globals,
                     frame_apply_vars, frame_revert_vars)


class nil(object):
    def __repr__(self):
        return "nil"
nil = nil()
is_nil = partial(is_, nil)


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
        #self._defined = dict(*args, **kwds)
        defined = dict(*args, **kwds)

        self._cells = dict((key, cell_from_value(val)) for
                           key, val in defined.iteritems())

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
        dup._cells = self._cells

        dup._outer_frame = None
        dup._outer_locals = None
        dup._outer_globals = None
        dup._outer_cells = None
        dup._inner_locals = None
        dup._inner_globals = None

        dup._alias_parent = self

        return dup


    def __getitem__(self, key):
        cell = self._cells.get(key, None)
        if not cell:
            raise KeyError(key)
        return cell_get_value(cell)


    def __setitem__(self, key, value):
        cell = self._cells.get(key, None)
        if not cell:
            cell = cell_from_value(value)
        else:
            cell_set_value(cell, value)


    def __delitem__(self, key):
        cell = self._cells.pop(key, None)
        if not cell:
            raise KeyError(key)


    def __contains__(self, key):
        return key in self._cells


    def in_use(self):
        """
        Boolean noting whether this scope is currently in-use
        """
        return self._outer_frame is not None


    def _frame_reapply(self):
        frame = self._outer_frame
        if frame:
            _unused = frame_apply_vars(frame, self._cells, nil)


    def _frame_apply(self):
        frame = self._outer_frame
        assert(frame is not None)

        fast, cells = frame_apply_vars(frame, self._cells, nil)
        self._outer_vars = fast
        self._outer_cells = cells

        inner_globals = None
        outer_globals = None
        varnames = frame.f_code.co_varnames

        # construct an inner_globals for bindings that we could not
        # assign as local variables, cell variables, or free variables
        for key, val in self._cells.iteritems():
            if key not in varnames:
                if inner_globals is None:
                    inner_globals = {}
                inner_globals[key] = cell_get_value(val)

        if inner_globals is not None:
            outer_globals = frame_swap_globals(frame, inner_globals, nil)

        self._inner_globals = inner_globals
        self._outer_globals = outer_globals


    def _frame_revert(self):
        frame = self._outer_frame
        assert(frame is not None)

        n = nil

        fast = self._outer_vars
        cells = self._outer_cells

        fast, cells = frame_revert_vars(frame, fast, cells, n)

        self._outer_vars = None
        self._outer_cells = None

        for key, val in fast.iteritems():
            if val is n:
                del self._cells[key]
            else:
                cell_set_value(self._cells[key], val)

        for key, val in cells.iteritems():
            if val is n:
                del self._cells[key]
            else:
                pass

        if self._inner_globals is not None:
            changes = frame_swap_globals(frame, self._outer_globals, n)
            for key, val in changes.iteritems():
                if val is n:
                    del self._cells[key]
                else:
                    cell_set_value(self._cells[key], val)

        self._inner_globals = None
        self._outer_globals = None


    def _refresh(self):
        """ refresh the values of our defined cells from the fast vars
        in our frame, if any. This happens automatically when the scope
        exits as well."""

        if not self._outer_frame:
            return

        # TODO: make a more direct version of this, that works with
        # deleted vars
        l = self._outer_frame.f_locals
        for key, val in l.iteritems():
            if key in self._cells:
                cell_set_value(self._cells[key], val)


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
            parent._refresh()

        self._frame_apply()

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
        # get a sync'd copy of its variables from the frame.
        parent = self._alias_parent
        if parent:
            parent._refresh()

        self._frame_revert()
        self._outer_frame = None

        # if we are an alias, we have to now tell the parent
        # that we've updated the shared defined dict, and have it
        # apply those variables into its frame
        if parent:
            parent._frame_reapply()

        return exc_type is None


# provide a happy little binding for the Scope class
let = Scope


def frame_swap_globals(frame, updates, nil):
    # TODO: move this into frame.c

    assert(frame is not None)

    glbls = frame.f_globals
    lcls = frame.f_locals
    originals = {}

    for key, val in updates.iteritems():
        if key in glbls:
            originals[key] = glbls[key]
            if val is nil:
                del glbls[key]
                del lcls[key]
            else:
                glbls[key] = val
                lcls[key] = val
        else:
            originals[key] = nil
            if val is nil:
                # nothing to do, this is a delete sentinel and it's
                # already not present.
                pass
            else:
                glbls[key] = val
                lcls[key] = val

    return originals


#
# The end.
