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


/**
   From the dict newcells, find cells in fast (named by their index in
   vars) that match, and replace the fast reference with the
   newcells[name] reference. Record swaps in the swapped dict.
 */
static inline void
fast_cells_swap(PyObject **fast, int offset, PyObject *vars,
		PyObject *newcells, PyObject *swapped) {

  PyObject *key, *newcell, *oldcell;
  int count = PyTuple_GET_SIZE(vars);
  int index;

  while (count-- ) {
    key = PyTuple_GET_ITEM(vars, count);
    newcell = PyObject_GetItem(newcells, key);

    if (newcell) {
      index = offset + count;
      oldcell = fast[index];
      fast[index] = newcell;

      PyObject_SetItem(swapped, key, oldcell);
      Py_DECREF(oldcell);

    } else {
      PyErr_Clear();
    }
  }
}


static PyObject *frame_revert_vars(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;
  PyObject *revert_vars, *revert_cells;
  PyObject *nil = NULL;

  if (! PyArg_ParseTuple(args, "O!O!O!O",
			 &PyFrame_Type, &frame,
			 &PyDict_Type, &revert_vars,
			 &PyDict_Type, &revert_cells,
			 &nil))
    return NULL;

  PyCodeObject *code = frame->f_code;
  PyObject **fast = frame->f_localsplus;
  PyObject *key, *newval, *oldval;
  int i, offset;

  PyObject *ret = PyTuple_New(2);
  PyObject *o_vars, *o_cells;

  o_vars = PyDict_New();
  o_cells = PyDict_New();

  PyTuple_SET_ITEM(ret, 0, o_vars);
  PyTuple_SET_ITEM(ret, 1, o_cells);

  // first we go through locals, and if we find a var matching a
  // defined name, we swap our value in and store the original in a
  // dictionary so we can restore it later. The scope stores all its
  // values wrapped in cells
  for (i = code->co_nlocals; i--; ) {
    key = PyTuple_GET_ITEM(code->co_varnames, i);
    newval = PyObject_GetItem(revert_vars, key);

    if (newval) {
      oldval = fast[i];
      if (newval == nil) {
	// nil is our sentinel value meaning that a var should be
	// cleared
	fast[i] = NULL;
	Py_DECREF(newval);
      } else {
	fast[i] = newval;
      }

      // nil used again here, if the var was previously unset, the
      // value is NULL, so we'll denote that by putting nil in its
      // place in the returned dict.
      PyObject_SetItem(o_vars, key, oldval? oldval: nil);
      Py_XDECREF(oldval);

    } else {
      PyErr_Clear();
    }
  }

  offset = code->co_nlocals;
  fast_cells_swap(fast, offset, code->co_cellvars, revert_cells, o_cells);

  offset += PyTuple_GET_SIZE(code->co_cellvars);
  fast_cells_swap(fast, offset, code->co_freevars, revert_cells, o_cells);

  return ret;
}


static PyObject *frame_apply_vars(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;
  PyObject *scopecells = NULL;
  PyObject *nil = NULL;

  if (! PyArg_ParseTuple(args, "O!O!O",
			 &PyFrame_Type, &frame,
			 &PyDict_Type, &scopecells,
			 &nil))
    return NULL;

  PyCodeObject *code = frame->f_code;
  PyObject **fast = frame->f_localsplus;
  PyObject *key, *newcell, *oldval;
  int i, offset;

  PyObject *o_vars, *o_cells;
  PyObject *ret = PyTuple_New(2);

  o_vars = PyDict_New();
  o_cells = PyDict_New();

  PyTuple_SET_ITEM(ret, 0, o_vars);
  PyTuple_SET_ITEM(ret, 1, o_cells);

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
  fast_cells_swap(fast, offset, code->co_cellvars, scopecells, o_cells);

  offset += PyTuple_GET_SIZE(code->co_cellvars);
  fast_cells_swap(fast, offset, code->co_freevars, scopecells, o_cells);

  return ret;
}


static PyMethodDef methods[] = {
  { "cell_from_value", cell_from_value, METH_VARARGS,
    "create a cell wrapping a value" },

  { "cell_get_value", cell_get_value, METH_VARARGS,
    "get a value from inside a cell" },

  { "cell_set_value", cell_set_value, METH_VARARGS,
    "set a cell's value" },

  { "frame_set_f_globals", frame_set_f_globals, METH_VARARGS,
    "set a frame's globals" },

  { "frame_apply_vars", frame_apply_vars, METH_VARARGS,
    ("replaces fast locals and cells with values and cells from the"
     " given dict. Returns a tuple of two dicts of original vals and"
     " cells.") },

  { "frame_revert_vars", frame_revert_vars, METH_VARARGS,
    ("reverts changes made by frame_apply_vars by restoring the"
     " values and cells given. Returns the values replaced") },

  { NULL, NULL, 0, NULL },
};


PyMODINIT_FUNC init_frame() {
  Py_InitModule("withscope._frame", methods);
}


/* The end. */
