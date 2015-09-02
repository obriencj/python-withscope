"""
Unit tests for withscope
"""


from unittest import TestCase
from withscope import let


class LetTest(TestCase):

    def test_simple_single(self):
        a = "tacos"
        b = "soup"

        with let(a="fajita"):
            self.assertEquals(a, "fajita")
            self.assertEquals(b, "soup")

        self.assertEquals(a, "tacos")
        self.assertEquals(b, "soup")


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

        a = [ "taco" ]
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

        self.assertEquals(get_a_1(), "taco")
        self.assertEquals(old_a_1(), None)

        self.assertEquals(get_a_2(), "fajita")
        self.assertEquals(old_a_2(), None)

        set_a_1("pizza")
        set_a_2("curry")

        self.assertEquals(get_a_1(), "pizza")
        self.assertEquals(old_a_1(), "taco")
        self.assertEquals(get_a_2(), "curry")
        self.assertEquals(old_a_2(), "fajita")

        self.assertEquals(a[0], "pizza")
        self.assertEquals(b[0], "taco")
        with scope:
            self.assertEquals(a[0], "curry")
            self.assertEquals(b[0], "fajita")


#
# The end.
