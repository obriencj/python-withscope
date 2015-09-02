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
  This is just to permit me to change the values of cells conveniently,
  which is absolutely necessary in order to pickle recursive function
  definitions.

  author: Christopher O'Brien  <obriencj@gmail.com>
*/


#include <Python.h>
#include <cellobject.h>
#include <frameobject.h>
#include <tupleobject.h>


static PyObject *frame_setlocals(PyObject *self, PyObject *args) {
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


static PyObject *frame_setglobals(PyObject *self, PyObject *args) {
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


static PyObject *frame_recreatecells(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;

  if (! PyArg_ParseTuple(args, "O!", &PyFrame_Type, &frame))
    return NULL;

  PyCodeObject *code = frame->f_code;
  PyObject **fast = frame->f_localsplus;
  Py_ssize_t j, offset;
  int ncells, nfreevars;
  PyObject *oldcell;

  offset = code->co_nlocals;

  ncells = PyTuple_GET_SIZE(code->co_cellvars);
  for (j = ncells; j--; ) {
    oldcell = fast[j + offset];
    fast[j + offset] = PyCell_New(PyCell_Get(oldcell));
    Py_DECREF(oldcell);
  }

  offset += ncells;

  nfreevars = PyTuple_GET_SIZE(code->co_freevars);
  for (j = nfreevars; j--; ) {
    oldcell = fast[j + offset];
    fast[j + offset] = PyCell_New(PyCell_Get(oldcell));
    Py_DECREF(oldcell);
  }

  Py_RETURN_NONE;
}


static PyObject *frame_getcells(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;
  PyObject *cells = NULL;

  if (! PyArg_ParseTuple(args, "O!", &PyFrame_Type, &frame))
    return NULL;

  PyCodeObject *code = frame->f_code;
  PyObject **fast = frame->f_localsplus;
  Py_ssize_t j, offset, index = 0;
  PyObject *oldcell;
  int ncells, nfreevars;

  ncells = PyTuple_GET_SIZE(code->co_cellvars);
  nfreevars = PyTuple_GET_SIZE(code->co_freevars);

  cells = PyTuple_New(ncells + nfreevars);

  offset = code->co_nlocals;
  for (j = ncells; j--; ) {
    oldcell = fast[j + offset];
    Py_INCREF(oldcell);
    PyTuple_SET_ITEM(cells, index++, oldcell);
  }

  offset += ncells;
  for (j = nfreevars; j--; ) {
    oldcell = fast[j + offset];
    Py_INCREF(oldcell);
    PyTuple_SET_ITEM(cells, index++, oldcell);
  }

  return cells;
}


static PyObject *frame_setcells(PyObject *self, PyObject *args) {
  PyFrameObject *frame = NULL;
  PyObject *cells = NULL;

  if (! PyArg_ParseTuple(args, "O!O!", &PyFrame_Type, &frame,
			 &PyTuple_Type, &cells))
    return NULL;

  PyCodeObject *code = frame->f_code;
  PyObject **fast = frame->f_localsplus;
  Py_ssize_t j, offset, index = 0;
  PyObject *oldcell, *newcell;
  int ncells, nfreevars;

  offset = code->co_nlocals;

  /* note, the order of the frame_setcells needs to be the same wonky
     order used by frame_getcells */

  ncells = PyTuple_GET_SIZE(code->co_cellvars);
  for (j = ncells; j--; ) {
    oldcell = fast[j + offset];
    newcell = PyTuple_GET_ITEM(cells, index++);
    Py_INCREF(newcell);
    fast[j + offset] = newcell;
    Py_DECREF(oldcell);
  }

  offset += ncells;

  nfreevars = PyTuple_GET_SIZE(code->co_freevars);
  for (j = nfreevars; j--; ) {
    oldcell = fast[j + offset];
    newcell = PyTuple_GET_ITEM(cells, index++);
    Py_INCREF(newcell);
    fast[j + offset] = newcell;
    Py_DECREF(oldcell);
  }

  Py_RETURN_NONE;
}


static PyMethodDef methods[] = {

  { "frame_setlocals", frame_setlocals, METH_VARARGS,
    "set a frame's locals" },

  { "frame_setglobals", frame_setglobals, METH_VARARGS,
    "set a frame's globals" },

  { "frame_recreatecells", frame_recreatecells, METH_VARARGS,
    "recreate a frame's cells with the same values" },

  { "frame_getcells", frame_getcells, METH_VARARGS,
    "get a frame's cells" },

  { "frame_setcells", frame_setcells, METH_VARARGS,
    "set a frame's cells" },

  { NULL, NULL, 0, NULL },
};


PyMODINIT_FUNC init_frame() {
  PyObject *mod;
  mod = Py_InitModule("withscope._frame", methods);
}


/* The end. */
