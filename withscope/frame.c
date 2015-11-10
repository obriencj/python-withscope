/*
  This library is free software; you can redistribute it and/or modify
  it under the terms of the GNU Lesser General Public License as
  published by the Free Software Foundation; either version 3 of the
  License, or (at your option) any later version.

  This library is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public
  License along with this library; if not, see
  <http://www.gnu.org/licenses/>.
*/


/**
   This enables the overridding of locals and cells in a call frame,
   and is used to enable the effect of pushing/popping local lexical
   scopes.

   TODO: there are all sorts of safety checks that need to be
   added. Type checking, length checking. I'll get to those at some
   point.

   author: Christopher O'Brien  <obriencj@gmail.com>
   license: LGPL v.3
*/


#include <Python.h>
#include <cellobject.h>
#include <frameobject.h>


static PyObject *cell_from_value(PyObject *self, PyObject *args) {
  PyObject *val = NULL;

  if (! PyArg_ParseTuple(args, "O", &val))
    return NULL;

  return PyCell_New(val);
}


static PyObject *cell_get_value(PyObject *self, PyObject *args) {
  PyObject *cell = NULL;

  if (! PyArg_ParseTuple(args, "O!", &PyCell_Type, &cell))
    return NULL;

  return PyCell_Get(cell);
}


static PyObject *cell_set_value(PyObject *self, PyObject *args) {
  PyObject *cell = NULL;
  PyObject *val = NULL;

  if (! PyArg_ParseTuple(args, "O!O", &PyCell_Type, &cell, &val))
    return NULL;

  PyCell_Set(cell, val);

  Py_RETURN_NONE;
}


/**
   Sets the locals dict for a call frame, and refreshes the fast
   access vars from that dict.
 */
static PyObject *frame_set_f_locals(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;
  PyObject *val = NULL;

  if (! PyArg_ParseTuple(args, "O!O", &PyFrame_Type, &frame, &val))
    return NULL;

  PyObject *old_locals = frame->f_locals;
  frame->f_locals = val;
  Py_INCREF(val);
  Py_DECREF(old_locals);

  PyFrame_LocalsToFast(frame, 1);

  Py_RETURN_NONE;
}


/**
   Sets the globals dict for a call frame
 */
static PyObject *frame_set_f_globals(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;
  PyObject *val = NULL;

  if (! PyArg_ParseTuple(args, "O!O", &PyFrame_Type, &frame, &val))
    return NULL;

  PyObject *old_globals = frame->f_globals;
  frame->f_globals = val;
  Py_INCREF(val);
  Py_DECREF(old_globals);

  Py_RETURN_NONE;
}


static PyObject *frame_apply_vars(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;
  PyObject *scopecells = NULL;
  PyObject *nil = NULL;

  if (! PyArg_ParseTuple(args, "O!OO", &PyFrame_Type, &frame,
			 &scopecells, &nil))
    return NULL;

  PyCodeObject *code = frame->f_code;
  PyObject **fast = frame->f_localsplus;
  int i, offset, ncells, nfreevars;
  PyObject *key, *newcell, *oldcell;
  PyObject *oldval;

  PyObject *o_vars, *o_cells, *o_free;
  PyObject *ret = PyTuple_New(3);

  o_vars = PyDict_New();
  o_cells = PyDict_New();
  o_free = PyDict_New();

  PyTuple_SET_ITEM(ret, 0, o_vars);
  PyTuple_SET_ITEM(ret, 1, o_cells);
  PyTuple_SET_ITEM(ret, 2, o_free);

  // first we go through locals, and if we find a var matching a
  // defined name, we swap our value in and store the original in a
  // dictionary so we can restore it later. The scope stores all its
  // values wrapped in cells
  for (i = code->co_nlocals; i--; ) {
    key = PyTuple_GET_ITEM(code->co_varnames, i);
    newcell = PyObject_GetItem(scopecells, key);

    if (newcell) {
      oldval = fast[i];
      fast[i] = PyCell_Get(newcell);
      PyObject_SetItem(o_vars, key, oldval? oldval: nil);
      Py_XDECREF(oldval);
      Py_DECREF(newcell);

    } else {
      PyErr_Clear();
    }
  }

  offset = code->co_nlocals;
  ncells = PyTuple_GET_SIZE(code->co_cellvars);

  for (i = ncells; i--; ) {
    key = PyTuple_GET_ITEM(code->co_cellvars, i);
    newcell = PyObject_GetItem(scopecells, key);

    if (newcell) {
      oldcell = fast[offset + i];
      fast[offset + i] = (newcell == nil? NULL: newcell);
      PyObject_SetItem(o_cells, key, oldcell? oldcell: nil);
      Py_XDECREF(oldcell);

    } else {
      PyErr_Clear();
    }
  }

  offset += ncells;
  nfreevars = PyTuple_GET_SIZE(code->co_freevars);

  for (i = nfreevars; i--; ) {
    key = PyTuple_GET_ITEM(code->co_freevars, i);
    newcell = PyObject_GetItem(scopecells, key);

    if (newcell) {
      oldcell = fast[offset + i];
      fast[offset + i] = (newcell == nil? NULL: newcell);
      PyObject_SetItem(o_free, key, oldcell? oldcell: nil);
      Py_XDECREF(oldcell);

    } else {
      PyErr_Clear();
    }
  }

  return ret;
}


static PyObject *frame_swap_fast_cells(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;
  PyObject *scopecells = NULL;

  if (! PyArg_ParseTuple(args, "O!O", &PyFrame_Type, &frame,
			 &scopecells))
    return NULL;

  PyCodeObject *code = frame->f_code;
  PyObject **fast = frame->f_localsplus;
  int j, offset, ncells, nfreevars;
  PyObject *key, *newcell, *oldcell;

  PyObject *swapped = PyDict_New();

  offset = code->co_nlocals;
  ncells = PyTuple_GET_SIZE(code->co_cellvars);

  for (j = ncells; j--; ) {
    key = PyTuple_GET_ITEM(code->co_cellvars, j);
    newcell = PyObject_GetItem(scopecells, key);
    if (newcell) {
      oldcell = fast[j + offset];
      fast[j + offset] = newcell;
      if (oldcell) {
	PyDict_SetItem(swapped, key, oldcell);
	Py_DECREF(oldcell);
      }
    } else {
      PyErr_Clear();
    }
  }

  offset += ncells;
  nfreevars = PyTuple_GET_SIZE(code->co_freevars);

  for (j = nfreevars; j--; ) {
    key = PyTuple_GET_ITEM(code->co_freevars, j);
    newcell = PyObject_GetItem(scopecells, key);
    if (newcell) {
      oldcell = fast[j + offset];
      fast[j + offset] = newcell;
      if (oldcell) {
	PyDict_SetItem(swapped, key, oldcell);
	Py_DECREF(oldcell);
      }
    } else {
      PyErr_Clear();
    }
  }

  return swapped;
}


static PyMethodDef methods[] = {
  { "cell_from_value", cell_from_value, METH_VARARGS,
    "create a cell wrapping a value" },

  { "cell_get_value", cell_get_value, METH_VARARGS,
    "get a value from inside a cell" },

  { "cell_set_value", cell_set_value, METH_VARARGS,
    "set a cell's value" },

  { "frame_set_f_locals", frame_set_f_locals, METH_VARARGS,
    "set a frame's locals" },

  { "frame_set_f_globals", frame_set_f_globals, METH_VARARGS,
    "set a frame's globals" },

  { "frame_swap_fast_cells", frame_swap_fast_cells, METH_VARARGS,
    ("replaces fast local cells with matching cells. Returns a dict"
     " of the original cells.") },

  { "frame_apply_vars", frame_apply_vars, METH_VARARGS,
    ("replaces fast locals and cells with values and cells from the"
     "given dict. Returns a tuple of two dicts of original vals and"
     "cells.") },

  { NULL, NULL, 0, NULL },
};


PyMODINIT_FUNC init_frame() {
  Py_InitModule("withscope._frame", methods);
}


/* The end. */
