# Overview of python-withscope

[![Build Status](https://travis-ci.org/obriencj/python-withscope.svg?branch=master)](https://travis-ci.org/obriencj/python-withscope)
[![Coverage Status](https://coveralls.io/repos/obriencj/python-withscope/badge.svg?branch=master)](https://coveralls.io/r/obriencj/python-withscope?branch=master)

This project embodies a completely mad idea: create a working `let`
syntax for [Python] to provide nested lexical scopes beyond the
existing global/local scopes. It should be regarded as a freak of
nature and not used for anything serious. I created this project
because I was pretty sure I could do so, but I wanted to be
certain. Also, I get a real buzz when something like this works, and
throwing back my head with screams of laughter is my chicken
soup for the soul.

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
from withscope import let

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
from withscope import let

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
Python. It's not a Pythonic thing to want, but that's [fancy] for
you.

[fancy]: https://www.youtube.com/watch?v=TNrtHf9jJB8

The managed interface looked very promising; the `with` keyword
visually identified a region of code, and had hooks to setup and
tear-down environmental changes, even in the event of exceptions.

My original experiments with this fell apart. I wanted to do the work
in pure Python, but rewriting locals and globals was just a mess. It
would require a native extension to swap those fields of the call
frame.


### Finally Getting Around To It

It was many months later that I was awake one night and thought, "hey,
let's give it a serious shot!" I hacked together a `Scope` class that
would fetch locals, wrap it into a layered dict with the
user-specified scope bindings, and stuff it into the frame and back
again.

This was good enough for very simple cases, but broke whenever
there was a new variable that hadn't already been defined. I solved
this case by also embedding lexical vars into a layered globals. Any
read references would fall through and fetch the correct value. Any
write references would be a local assignment. At the end of the scope,
the layered globals could be discarded as useless.

I encountered a few issues. For example, when creating a closure, the
cell vars are harvested pre-created from the frame. This meant that
closures would revert to the original value when the scope closed,
even if the closure was captured inside the new scope. I got around
this by re-creating the appropriate cells when pushing a new scope,
but with the same values. There was also an issue with how the `del`
statement behaved, which caused me a great deal of frustration and
eventually forced me to accept less-than-ideal behavior as expected. I
wanted `del` of a lexical name to cause later references to
fall-through to any prior definition. But there is no way for me to
hook additional behavior to that statement at the point it occurs! I
could detect it later, when for examples `locals()` would be called. I
had to abandon fall-through and just accept that a `del` of a lexical
name from within a scope would cause the name to be undefined until
the scope exited.


### What's Next?

I've learned a lot about the many ways that Python stores runtime
variables. They're all over the place. I've also learned some
interesting things about frames, the allocator, and some of the
bytecode implementation details. I'd like to take all of that and
write it up for educational purposes, perhaps as a blog entry.

I have a few things I might like to scoot over into the extension and
out of the python module, but they work as-is.


## Requirements

* [Python] 2.6 or later (no support for Python 3, the underlying
  function fields differ a bit)

In addition, the following tools are used in building, testing, or
generating documentation from the project sources.

* [Setuptools]
* [Coverage.py]

These are all available in most linux distributions (eg. [Fedora]), and
for OSX via [MacPorts].

[setuptools]: http://pythonhosted.org/setuptools/

[coverage.py]: http://nedbatchelder.com/code/coverage/

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

You may check code coverage via [coverage.py], invoked as:

```bash
# generates coverage data in .coverage
coverage run --source=withscope setup.py test

# creates an html report from the above in htmlcov/index.html
coverage html
```

I've setup [travis-ci] and [coveralls.io] for this project, so tests
are run automatically, and coverage is computed then. Results are
available online:

* [python-withscope on Travis-CI][withscope-travis]
* [python-withscope on Coveralls.io][withscope-coveralls]

[travis-ci]: https://travis-ci.org

[coveralls.io]: https://coveralls.io

[withscope-travis]: https://travis-ci.org/obriencj/python-withscope

[withscope-coveralls]: https://coveralls.io/r/obriencj/python-withscope


## TODO

* type-checking in the withscope._frame extension
* Is a documentation branch worthwhile?
* Is a Python 3 branch worthwhile?
* write more examples, eg. depicting the use of `Scope.alias()`
* a scope that references an object's attributes via getattr (for use
  with something like the option object from `optparser`)
* profiling and optimizations? Do I care?


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
