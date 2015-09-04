# Overview of python-withscope

This is a completely mad idea, to create a working "let" syntax for
[Python]. It should be regarded as a freak of nature and not used for
anything serious. I did it because I was pretty sure I could, but I
wanted to be certain.

[python]: http://python.org "Python"


## Using withscope

```python
from withscope import let

a = "taco"
with let(a="pizza", b="beer"):
    print "%s and %s" % (a, b) # >>> "pizza and beer"

print a # >>> "taco"
print b # >>> NameError: name 'b' is not defined
```

You can also save scopes and re-enter them whenever you feel like it.

```python

with let(a="pizza", b="beer") as my_scope:
	print "actually, not that hungry right now"
	a = "popcorn"
	b = "water"

print a # >>> NameError: name 'a' is not defined

with my_scope:
	print "%s and %s" % (a, b) # >>> "popcorn and water"
```

Yes really, that works. It will correctly fall-through to outer scopes
as well

```python

monster = "godzilla"
city = "Tokyo"

print "%s is attacking %s" % (monster, city)
# >>> "godzilla is attacking Tokyo"

with let(monster="mothra"):
	print "%s is attacking %s" % (monster, city)
	# >>> "mothra is attacking Tokyo"

	city = "New York"

print "%s is attacking %s" % (monster, city)
# >>> "godzilla is attacking New York"
```

It also functions correctly with closures, giving you a new set of
cells to capture while you're inside a new scope, then returning the
original cells to their place when the scope ends.


## The Story

I wanted some way to push and subsequently pop a lexical scope in
Python. It's not a Pythonic thing to want, but that's fancy for you.

The managed interface looked very promising -- the `with` keyword
visually identified a region of code, and had hooks to setup and
tear-down environmental changes, even if there were exceptions.

My original experiments with this fell apart. I wanted to do the work
in pure Python, but rewriting locals and globals was just a mess. It
would require a native extension to swap those fields of the call
frame.


### Finally Getting Around To It

It was months and months later that I was awake one night and thought,
"hey, let's give it a serious shot!" I hacked together a Scope class
that would fetch locals, wrap it into a layered dict with the
user-specified scope bindings, and stuff it into the frame and back
again.

This was good enough for very simple cases, but broke whenever
there was a new variable that hadn't already been defined. I solved
this case by also embedding lexical vars into a layered globals. Any
read references would fall through and fetch the correct value. Any
write references would be a local assignment. At the end of the scope,
the layered globals could be discarded as useless.

The next issue I encountered was a surprise -- when creating a
closure, the cell vars are harvested pre-created from the frame. This
meant that closures would revert to the original value when the scope
closed, even if the closure was captured inside the new scope. I got
around this by re-creating all the cells when pushing a new scope, but
with the same values. Any closure of those cells would capture a cell
unique to the scope, and then I'd put the original cells back in the
frame at scope exit. The closures inside the scope saw their own
cells, and the closures outside the scope saw the originals.

### What's Next

Well, the cell hacking seemed good, but it's actually buggy in that
it's duplicating cells for all cellvars, not just the ones in the
scope. This means fall-through isn't working like it should. I need to
only recreate cells that have keys in the scope defined variables.

I am also unhappy with the behavior of `del var` when inside a
scope. It should be removing the binding of the scope, thus causing
fall-through. That isn't the case, unfortunately. I believe to make
this work correctly, I will need to coalesc my frame modifications
into a full frame swap.

I will grab the current frame inside the `__enter__` method, and swap
the `f_back` frame out for a duplicate which has my own
locals/globals/cells/fast embedded, with the same code and index
references. Execution will continue in this new shadow frame, and then
the `__exit__` method will be triggered. At that point, I will again
grab the current frame and swap its `f_back` out, this time for the
original return frame, but with an updated code index. Pretty sure
that will work, anyway.

I am also strongly considering re-implementing `LayeredMapping`
natively, just because it's probably the slowest part of this whole
thing, and it makes for ugly-to-read Python.


## Requirements

* [Python] 2.6 or later (no support for Python 3, the underlying
  function fields differ a bit)

In addition, following tools are used in building, testing, or
generating documentation from the project sources.

* [Setuptools]

These are all available in most linux distributions (eg. [Fedora]), and
for OSX via [MacPorts].

[setuptools]: http://pythonhosted.org/setuptools/

[fedora]: http://fedoraproject.org/

[macports]: http://www.macports.org/


## Building

This module uses [setuptools], so simply run the following to build
the project.

```bash
python setup.py build
```


### Testing

Tests are written as `unittest` test cases. If you'd like to run the
tests, simply invoke:

```bash
python setup.py test
```


## Author

Christopher O'Brien <obriencj@gmail.com>

If this project interests you, you can read about more of my hacks and
ideas on [on my blog](http://obriencj.preoccupied.net).


## License

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
