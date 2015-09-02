#! /usr/bin/env python2


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
Hack stack frames to provide local scopes via the managed
interface.

author: Christopher O'Brien  <obriencj@gmail.com>
license: LGPL v.3
"""


from setuptools import setup, Extension

ext = [ Extension("withscope._frame", ["withscope/frame.c"]), ]

setup( name = "withscope",
       version = "0.9.0",

       packages = [ "withscope" ],

       ext_modules = ext,

       test_suite = "tests",

       # PyPI information
       author = "Christopher O'Brien",
       author_email = "obriencj@gmail.com",
       url = "https://github.com/obriencj/python-withscope",
       license = "GNU Lesser General Public License",

       description = "Hack stack frames to provide local scopes via"
       " the managed interface.",

       provides = [ "withscope" ],
       requires = [],
       platforms = [ "python2 >= 2.6" ],

       zip_safe = True,

       classifiers = ["Intended Audience :: Developers",
                      "Programming Language :: Python :: 2",
                      "Topic :: Software Development"], )

#
# The end.
