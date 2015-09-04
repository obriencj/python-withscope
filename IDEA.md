
# Original Idea

I wanted some way to push and subsequently pop a lexical scope in
Python. It's not a Pythonic thing to want, but that's fancy for you.

The managed interface looked very promising -- the `with` keyword
visually identified a region of code, and had hooks to setup and
tear-down environmental changes, even if there were exceptions.

My original experiments with this fell apart. I wanted to do the work
in pure Python, but rewriting locals and globals was just a mess. It
would require a native extension to swap those fields of the call
frame.

# Finally Getting Around To It

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

# Next

Well, the cell hacking seemed good, but it's actually buggy in that
it's duplicating cells for all cellvars, not just the ones in the
scope. This means fall-through isn't working like it should. I need to
only recreate cells that have keys in the scope defined variables.

I am also unhappy with the behavior of `del var` when inside a
scope. It should be removing the binding of the scope, thus causing
fall-through. That isn't the case, unfortunately. I believe to make
this work correctly, I will need to coalesc my frame modifications
into a full frame swap.

I will grab the current frame inside the __enter__ method, and swap
the f_back frame out for a duplicate which has my own
locals/globals/cells/fast embedded, with the same code and index
references. Execution will continue in this new shadow frame, and then
the __exit__ method will be triggered. At that point, I will again
grab the current frame and swap its f_back out, this time for the
original return frame, but with an updated code index. Pretty sure
that will work, anyway.
