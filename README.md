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


## TODO

I could probably optimize it? Or not? Who cares?

Currently it modifies the frame -- it might be better to actually
create a new frame, swap it into place, and then swap it back out
again. Something to think about.


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
