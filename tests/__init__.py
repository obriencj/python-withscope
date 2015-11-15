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
Unit tests for withscope

:author: Christopher O'Brien  <obriencj@gmail.com>
:license: LGPL v.3
"""


from unittest import TestCase
from withscope import let, ScopeInUse, ScopeMismatch


# global values to check for shadowing
_a = "tacos"
_b = "soda"


class LetTest(TestCase):


    def test_simple_single(self):
        a = "tacos"
        b = "soda"

        with let(a="fajita"):
            self.assertEquals(a, "fajita")
            self.assertEquals(b, "soda")

        self.assertEquals(a, "tacos")
        self.assertEquals(b, "soda")


    def test_nested_let(self):
        a = "tacos"
        b = "soup"
        c = "cake"

        with let(a="fajita"):
            with let(c="bread"):
                self.assertEquals(a, "fajita")
                self.assertEquals(b, "soup")
                self.assertEquals(c, "bread")

                c = "cupcake"
                self.assertEquals(c, "cupcake")

            self.assertEquals(a, "fajita")
            self.assertEquals(b, "soup")
            self.assertEquals(c, "cake")
        self.assertEquals(a, "tacos")
        self.assertEquals(b, "soup")
        self.assertEquals(c, "cake")


    def test_nested_assign(self):
        """
        tests that direct assignment of a non-re-scoped variable correctly
        sets the right valueq
        """

        a = "tacos"
        b = "soup"
        c = "cake"

        with let():
            a = "fajita"
            with let():
                self.assertEquals(a, "fajita")
                b = "stew"
            self.assertEquals(a, "fajita")
            self.assertEquals(b, "stew")
        self.assertEquals(a, "fajita")
        self.assertEquals(b, "stew")
        self.assertEquals(c, "cake")


    def test_reusable_scope(self):

        scope = let(a="tacos", b="soup", c="cake")
        d = "godzilla"

        with scope:
            self.assertEquals(a, "tacos")
            self.assertEquals(b, "soup")
            self.assertEquals(c, "cake")
            self.assertEquals(d, "godzilla")

            a = "fajita"
            b = "stew"
            d = "mothra"

        self.assertFalse("a" in locals())
        self.assertFalse("b" in locals())
        self.assertFalse("c" in locals())
        self.assertTrue("d" in locals())

        self.assertFalse("a" in globals())
        self.assertFalse("b" in globals())
        self.assertFalse("c" in globals())
        self.assertFalse("d" in globals())

        self.assertEquals(d, "mothra")

        with scope:
            self.assertEquals(a, "fajita")
            self.assertEquals(b, "stew")
            self.assertEquals(c, "cake")
            self.assertEquals(d, "mothra")


    def test_closure(self):
        """
        This tests that closures are created over the correct scope, and
        that the correct cells are made available.
        """

        a = [ "tacos" ]
        b = [ None ]

        def get_a_1():
            return a[0]
        def set_a_1(new_a):
            b[0] = a[0]
            a[0] = new_a
        def old_a_1():
            return b[0]

        with let(a = ["fajita"], b = [None]) as scope:
            self.assertEquals(a[0], "fajita")
            def get_a_2():
                return a[0]
            def set_a_2(new_a):
                b[0] = a[0]
                a[0] = new_a
            def old_a_2():
                return b[0]
            self.assertEquals(get_a_2(), "fajita")

        self.assertEquals(get_a_1(), "tacos")
        self.assertEquals(old_a_1(), None)

        self.assertEquals(get_a_2(), "fajita")
        self.assertEquals(old_a_2(), None)

        set_a_1("pizza")
        set_a_2("curry")

        self.assertEquals(get_a_1(), "pizza")
        self.assertEquals(old_a_1(), "tacos")
        self.assertEquals(get_a_2(), "curry")
        self.assertEquals(old_a_2(), "fajita")

        self.assertEquals(a[0], "pizza")
        self.assertEquals(b[0], "tacos")
        with scope:
            self.assertEquals(a[0], "curry")
            self.assertEquals(b[0], "fajita")


    def test_del_fast_local(self):
        a = "tacos"

        # testing `DELETE_NAME` opcode. Since `a` is already defined
        # above when we push our scope `a` will be considered a fast
        # local, and calling `del a` will trigger `DELETE_NAME`
        with let(a="pizza") as scope:
            self.assertEquals(a, "pizza")
            del a

            # this doesn't work -- I cannot make it fall-through,
            # there's nothing that lets me catch the DELETE_NAME
            # opcode's execution, and the f_locals.__delitem__ is
            # only triggered when the locals() builtin is called
            #self.assertEquals(a, "taco")

            self.assertTrue("a" not in locals())

        self.assertEquals(a, "tacos")

        with scope:
            self.assertEquals(a, "tacos")

        #print locals()
        self.assertEquals(a, "tacos")


    def test_del_global(self):
        # testing `DELETE_GLOBAL` opcode. Since `b` is NOT already
        # defined when we push our scope, AND since `b` is not
        # ASSIGNED to anything in our block below, `b` will be
        # injected as a global -- read-only from our perspective,
        # because if the compiler had detected a write, it would have
        # made it into fast locals. This explanation is awful, rewrite
        # it.

        self.assertTrue("a" not in locals())
        self.assertTrue("a" not in globals())

        with let(a="pizza") as scope:
            self.assertEquals(a, "pizza")
            del a

            self.assertTrue("a" not in locals())

        self.assertTrue("a" not in locals())
        self.assertTrue("a" not in globals())


    def test_alias(self):
        a = "hungry"
        b = "thirsty"

        # here we'll set up a helper function that will activate
        # a given scope, and then assign the a and b values to the
        # food and drink we supply.
        def set_in_scope(my_scope, food, drink):
            with my_scope:
                a = food
                b = drink

        with let(a="pizza", b="beer") as scope:

            # attempting to activate the existing scope prevents
            # us from setting the rat poison
            self.assertRaises(ScopeInUse, set_in_scope,
                              scope, "rat", "poison")

            self.assertEquals(a, "pizza")
            self.assertEquals(b, "beer")

            # instead, we alias the existing active scope, and we can
            # happily use it instead. When it exits, our scope is
            # refreshed with any values that might have changed via
            # the alias.
            capture = scope.alias()
            set_in_scope(capture, "tacos", "soda")

            self.assertEquals(a, "tacos")
            self.assertEquals(b, "soda")

        self.assertEquals(a, "hungry")
        self.assertEquals(b, "thirsty")


    def test_mismatch(self):
        scope = let(a="pizza", b="beer")

        scope.__enter__()
        self.assertTrue(scope.in_use())

        def closer():
            scope.__exit__(None, None, None)

        # calling closer executes the scope exit inside closer's frame
        # rather than this frame, which is a mismatch.
        self.assertRaises(ScopeMismatch, closer)

        # we need to clean up that __enter__ so globals isn't a mess
        # for later tests
        scope.__exit__(None, None, None)

        with scope.alias():
            self.assertEquals(a, "pizza")
            self.assertEquals(b, "beer")


    def test_with_globals(self):
        self.assertEquals(_b, "soda")

        _a = "pizza"
        with let(_b="beer"):
            self.assertEquals(_a, "pizza")
            self.assertEquals(_b, "beer")

            # make sure we did NOT munge _a into globals, since we
            # didn't need to do so
            self.assertEquals(globals()["_a"], "tacos")

            # since _b was not in co_varnames, it was munged into
            # globals for this scope
            self.assertEquals(globals()["_b"], "beer")

        # check that _b was returned to the original global val
        self.assertEquals(globals()["_b"], "soda")


#
# The end.
