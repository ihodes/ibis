# Copyright 2014 Cloudera Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import itertools
import operator

from ibis.common import IbisTypeError
import ibis.expr.api as api
import ibis.expr.types as ir
import ibis.expr.operations as ops
import ibis

from ibis.compat import unittest
from ibis.expr.tests.mocks import MockConnection, BasicTestCase

from ibis.tests.util import assert_equal


class TestLiterals(BasicTestCase, unittest.TestCase):

    def test_null(self):
        expr = ibis.literal(None)
        assert isinstance(expr, ir.NullScalar)
        assert isinstance(expr.op(), ir.NullLiteral)

        expr2 = ibis.null()
        assert_equal(expr, expr2)

    def test_boolean(self):
        val = True
        expr = ibis.literal(val)
        self._check_literal(expr, api.BooleanScalar, val)

        val = False
        expr = ibis.literal(val)
        self._check_literal(expr, api.BooleanScalar, val)

    def test_float(self):
        val = 1.5
        expr = ibis.literal(val)
        self._check_literal(expr, api.DoubleScalar, val)

    def test_string(self):
        val = 'foo'
        expr = ibis.literal(val)
        self._check_literal(expr, api.StringScalar, val)

    def _check_literal(self, expr, ex_klass, val):
        assert isinstance(expr, ex_klass)

        arg = expr.op()
        assert isinstance(arg, ir.Literal)
        assert arg.value == val

        # Console formatting works
        repr(expr)

    def test_unicode(self):
        # UTF-8 support in Impala non-existent at the moment?
        pass

    def test_int_literal_cases(self):
        cases = [
            (5, 'int8'),
            (127, 'int8'),
            (128, 'int16'),
            (32767, 'int16'),
            (32768, 'int32'),
            (2147483647, 'int32'),
            (2147483648, 'int64'),
            (-5, 'int8'),
            (-128, 'int8'),
            (-129, 'int16'),
            (-32769, 'int32'),
            (-2147483649, 'int64'),
            (1.5, 'double'),
            ('foo', 'string')
        ]

        for value, ex_type in cases:
            expr = ibis.literal(value)
            klass = ir.scalar_type(ex_type)
            assert isinstance(expr, klass)
            assert isinstance(expr.op(), ir.Literal)
            assert expr.op().value is value

    def test_literal_list(self):
        what = [1, 2, 1000]
        expr = api.as_value_expr(what)

        assert isinstance(expr, ir.ArrayExpr)
        assert isinstance(expr.op(), ir.ValueList)
        assert isinstance(expr.op().values[2], ir.Int16Scalar)

        # it works!
        repr(expr)

    def test_mixed_arity(self):
        table = self.table
        what = ["bar", table.g, "foo"]
        expr = api.as_value_expr(what)

        values = expr.op().values
        assert isinstance(values[1], ir.StringArray)

        # it works!
        repr(expr)


class TestContains(BasicTestCase, unittest.TestCase):

    def test_isin_notin_list(self):
        vals = [1, 2, 3]

        expr = self.table.a.isin(vals)
        not_expr = self.table.a.notin(vals)

        assert isinstance(expr, ir.BooleanArray)
        assert isinstance(expr.op(), ops.Contains)

        assert isinstance(not_expr, ir.BooleanArray)
        assert isinstance(not_expr.op(), ops.NotContains)

    def test_isin_not_comparable(self):
        pass

    def test_isin_array_expr(self):
        #
        pass

    def test_isin_invalid_cases(self):
        # For example, array expression in a list of values, where the inner
        # array values originate from some other table
        pass

    def test_isin_notin_scalars(self):
        a, b, c = [ibis.literal(x) for x in [1, 1, 2]]

        result = a.isin([1, 2])
        assert isinstance(result, ir.BooleanScalar)

        result = a.notin([b, c])
        assert isinstance(result, ir.BooleanScalar)

    def test_isin_null(self):
        pass

    def test_negate_isin(self):
        # Should yield a NotContains
        pass

    def test_scalar_isin_list_with_array(self):
        val = ibis.literal(2)

        options = [self.table.a, self.table.b, self.table.c]

        expr = val.isin(options)
        assert isinstance(expr, ir.BooleanArray)

        not_expr = val.notin(options)
        assert isinstance(not_expr, ir.BooleanArray)


class TestDistinct(unittest.TestCase):

    def setUp(self):
        self.con = MockConnection()
        self.table = self.con.table('functional_alltypes')

    def test_distinct_basic(self):
        expr = self.table.distinct()
        assert isinstance(expr.op(), ops.Distinct)
        assert isinstance(expr, ir.TableExpr)
        assert expr.op().table is self.table

        expr = self.table.string_col.distinct()
        assert isinstance(expr.op(), ops.DistinctArray)
        assert isinstance(expr, ir.StringArray)

    # def test_distinct_array_interactions(self):
    # TODO

    # array cardinalities / shapes are likely to be different.
    #     a = self.table.int_col.distinct()
    #     b = self.table.bigint_col

    #     self.assertRaises(ir.RelationError, a.__add__, b)

    def test_distinct_count(self):
        result = self.table.string_col.distinct().count()
        expected = self.table.string_col.nunique().name('count')
        assert_equal(result, expected)
        assert isinstance(result.op(), ops.CountDistinct)

    def test_distinct_unnamed_array_expr(self):
        table = ibis.table([('year', 'int32'),
                            ('month', 'int32'),
                            ('day', 'int32')], 'foo')

        # it works!
        expr = (ibis.literal('-')
                .join([table.year.cast('string'),
                       table.month.cast('string'),
                       table.day.cast('string')])
                .distinct())
        repr(expr)

    def test_distinct_count_numeric_types(self):
        table = self.table
        metric = (table.bigint_col.distinct().count()
                  .name('unique_bigints'))

        table.group_by('string_col').aggregate(metric)

    def test_nunique(self):
        expr = self.table.string_col.nunique()
        assert isinstance(expr.op(), ops.CountDistinct)

    def test_project_with_distinct(self):
        pass


class TestNullOps(BasicTestCase, unittest.TestCase):

    def test_isnull(self):
        expr = self.table['g'].isnull()
        assert isinstance(expr, api.BooleanArray)
        assert isinstance(expr.op(), ops.IsNull)

        expr = ibis.literal('foo').isnull()
        assert isinstance(expr, api.BooleanScalar)
        assert isinstance(expr.op(), ops.IsNull)

    def test_notnull(self):
        expr = self.table['g'].notnull()
        assert isinstance(expr, api.BooleanArray)
        assert isinstance(expr.op(), ops.NotNull)

        expr = ibis.literal('foo').notnull()
        assert isinstance(expr, api.BooleanScalar)
        assert isinstance(expr.op(), ops.NotNull)

    def test_null_literal(self):
        pass


class TestMathUnaryOps(BasicTestCase, unittest.TestCase):

    def test_log_variants(self):
        opnames = ['ln', 'log', 'log2', 'log10']

        columns = ['a', 'b', 'c', 'd', 'e', 'f']

        for opname in opnames:
            def f(x):
                return getattr(x, opname)()

            for c in columns:
                result = f(self.table[c])
                assert isinstance(result, api.DoubleArray)

                # is this what we want?
                # assert result.get_name() == c

            assert isinstance(f(ibis.literal(5)), api.DoubleScalar)
            assert isinstance(f(ibis.literal(5.5)), api.DoubleScalar)

            klass = getattr(ops, opname.capitalize())
            with self.assertRaises(IbisTypeError):
                if opname == 'log':
                    klass(self.table['g'], None).to_expr()
                else:
                    klass(self.table['g']).to_expr()

            # boolean not implemented for these
            with self.assertRaises(IbisTypeError):
                f(self.table['h'])

    def test_exp(self):
        pass

    def test_sqrt(self):
        pass

    def test_trig_functions(self):
        pass

    def test_round(self):
        pass


class TestTypeCasting(BasicTestCase, unittest.TestCase):

    def test_cast_same_type_noop(self):
        col = self.table['g']
        result = col.cast('string')
        assert result is col

    def test_string_to_number(self):
        types = ['int8', 'int32', 'double', 'float']

        for t in types:
            c = 'g'
            casted = self.table[c].cast(t)
            assert isinstance(casted, ir.array_type(t))

            casted_literal = ibis.literal('5').cast(t).name('bar')
            assert isinstance(casted_literal, ir.scalar_type(t))
            assert casted_literal.get_name() == 'bar'

    def test_number_to_string(self):
        cols = ['a', 'b', 'c', 'd', 'e', 'f', 'h']
        for c in cols:
            casted = self.table[c].cast('string')
            assert isinstance(casted, api.StringArray)

        casted_literal = ibis.literal(5).cast('string').name('bar')
        assert isinstance(casted_literal, api.StringScalar)
        assert casted_literal.get_name() == 'bar'

    def test_casted_exprs_are_unnamed(self):
        expr = self.table.f.cast('string')
        with self.assertRaises(Exception):
            expr.get_name()

        # it works! per GH #396
        expr.value_counts()


class TestBooleanUnaryOps(BasicTestCase, unittest.TestCase):

    def test_nonzero(self):
        pass

    def test_negate(self):
        for name in self.int_cols + self.float_cols + self.bool_cols:
            col = self.table[name]
            result = -col
            assert isinstance(result, type(col))
            assert isinstance(result.op(), ops.Negate)

        result = -ibis.literal(False)
        assert isinstance(result, api.BooleanScalar)
        assert isinstance(result.op(), ops.Negate)

    def test_isnull_notnull(self):
        pass


class TestComparisons(BasicTestCase, unittest.TestCase):

    def test_numbers_compare_numeric_literal(self):
        opnames = ['lt', 'gt', 'ge', 'le', 'eq', 'ne']

        ex_op_class = {
            'eq': ops.Equals,
            'ne': ops.NotEquals,
            'le': ops.LessEqual,
            'lt': ops.Less,
            'ge': ops.GreaterEqual,
            'gt': ops.Greater,
        }

        columns = ['a', 'b', 'c', 'd', 'e', 'f']

        cases = [2, 2 ** 9, 2 ** 17, 2 ** 33, 1.5]
        for opname, cname, val in itertools.product(opnames, columns, cases):
            f = getattr(operator, opname)
            col = self.table[cname]

            result = f(col, val)
            assert isinstance(result, api.BooleanArray)

            assert isinstance(result.op(), ex_op_class[opname])

    def test_boolean_comparisons(self):
        bool_col = self.table['h']

        result = bool_col == True  # noqa
        assert isinstance(result, api.BooleanArray)

        result = bool_col == False  # noqa
        assert isinstance(result, api.BooleanArray)

    def test_string_comparisons(self):
        string_col = self.table['g']

        ops = ['lt', 'gt', 'ge', 'le', 'eq', 'ne']

        for opname in ops:
            f = getattr(operator, opname)
            result = f(string_col, 'foo')
            assert isinstance(result, api.BooleanArray)

    def test_boolean_logical_ops(self):
        expr = self.table['a'] > 0
        ops = ['xor', 'or_', 'and_']

        for opname in ops:
            f = getattr(operator, opname)
            result = f(expr, self.table['h'])
            assert isinstance(result, api.BooleanArray)

            result = f(expr, True)
            refl_result = f(True, expr)
            assert isinstance(result, api.BooleanArray)
            assert isinstance(refl_result, api.BooleanArray)

            true = ibis.literal(True)
            false = ibis.literal(False)

            result = f(true, false)
            assert isinstance(result, api.BooleanScalar)

    def test_string_compare_numeric_array(self):
        self.assertRaises(TypeError, self.table.g.__eq__, self.table.f)
        self.assertRaises(TypeError, self.table.g.__eq__, self.table.c)

    def test_string_compare_numeric_literal(self):
        self.assertRaises(TypeError, self.table.g.__eq__, ibis.literal(1.5))
        self.assertRaises(TypeError, self.table.g.__eq__, ibis.literal(5))

    def test_between(self):
        result = self.table.f.between(0, 1)

        assert isinstance(result, ir.BooleanArray)
        assert isinstance(result.op(), ops.Between)

        # it works!
        result = self.table.g.between('a', 'f')
        assert isinstance(result, ir.BooleanArray)

        result = ibis.literal(1).between(self.table.a, self.table.c)
        assert isinstance(result, ir.BooleanArray)

        result = ibis.literal(7).between(5, 10)
        assert isinstance(result, ir.BooleanScalar)

        # Cases where between should immediately fail, e.g. incomparables
        self.assertRaises(TypeError, self.table.f.between, '0', '1')
        self.assertRaises(TypeError, self.table.f.between, 0, '1')
        self.assertRaises(TypeError, self.table.f.between, '0', 1)


class TestBinaryArithOps(BasicTestCase, unittest.TestCase):

    def test_binop_string_type_error(self):
        # Strings are not valid for any numeric arithmetic
        ints = self.table['a']
        strs = self.table['g']

        ops = ['add', 'mul', 'div', 'sub']
        for name in ops:
            f = getattr(operator, name)
            self.assertRaises(TypeError, f, ints, strs)
            self.assertRaises(TypeError, f, strs, ints)

    def test_add_literal_promotions(self):
        cases = [
            ('a', 0, 'int8'),
            ('a', 5, 'int16'),
            ('a', 100000, 'int32'),
            ('a', -100000, 'int32'),

            ('a', 1.5, 'double'),

            ('b', 0, 'int16'),
            ('b', 5, 'int32'),
            ('b', -5, 'int32'),

            ('c', 0, 'int32'),
            ('c', 5, 'int64'),
            ('c', -5, 'int64'),

            # technically this can overflow, but we allow it
            ('d', 5, 'int64')
        ]
        self._check_literal_promote_cases(operator.add, cases)

    def test_multiply_literal_promotions(self):
        cases = [
            ('a', 0, 'int8'),
            ('a', 5, 'int16'),
            ('a', 2 ** 24, 'int32'),
            ('a', -2 ** 24 + 1, 'int32'),

            ('a', 1.5, 'double'),

            ('b', 0, 'int16'),
            ('b', 5, 'int32'),
            ('b', -5, 'int32'),
            ('c', 0, 'int32'),
            ('c', 5, 'int64'),
            ('c', -5, 'int64'),

            # technically this can overflow, but we allow it
            ('d', 5, 'int64')
        ]
        self._check_literal_promote_cases(operator.mul, cases)

    def test_subtract_literal_promotions(self):
        cases = [
            ('a', 0, 'int8'),
            ('a', 5, 'int16'),
            ('a', 100000, 'int32'),
            ('a', -100000, 'int32'),

            ('a', 1.5, 'double'),

            ('b', 0, 'int16'),
            ('b', 5, 'int32'),
            ('b', -5, 'int32'),
            ('c', 0, 'int32'),
            ('c', 5, 'int64'),
            ('c', -5, 'int64'),

            # technically this can overflow, but we allow it
            ('d', 5, 'int64')
        ]
        self._check_literal_promote_cases(operator.sub, cases)

    def test_divide_literal_promotions(self):
        cases = [
            ('a', 5, 'double'),
            ('a', 1.5, 'double'),
            ('b', 5, 'double'),
            ('b', -5, 'double'),
            ('c', 5, 'double'),
        ]
        self._check_literal_promote_cases(operator.div, cases)

    def test_pow_literal_promotions(self):
        cases = [
            ('a', 0, 'int8'),
            ('b', 0, 'int16'),
            ('c', 0, 'int32'),
            ('d', 0, 'int64'),
            ('e', 0, 'float'),
            ('f', 0, 'double'),

            ('a', 2, 'int16'),
            ('b', 2, 'int32'),
            ('c', 2, 'int64'),
            ('d', 2, 'int64'),

            ('a', 1.5, 'double'),
            ('b', 1.5, 'double'),
            ('c', 1.5, 'double'),
            ('d', 1.5, 'double'),

            ('a', -2, 'double'),
            ('b', -2, 'double'),
            ('c', -2, 'double'),
            ('d', -2, 'double'),

            ('e', 2, 'float'),
            ('f', 2, 'double')
        ]
        self._check_literal_promote_cases(operator.pow, cases)

    def _check_literal_promote_cases(self, op, cases):
        for name, val, ex_type in cases:
            col = self.table[name]

            result = op(col, val)
            ex_class = ir.array_type(ex_type)
            assert isinstance(result, ex_class)

            result = op(val, col)
            ex_class = ir.array_type(ex_type)
            assert isinstance(result, ex_class)

    def test_add_array_promotions(self):
        pass

    def test_subtract_array_promotions(self):
        pass

    def test_multiply_array_promotions(self):
        pass

    def test_divide_array_promotions(self):
        pass

    def test_string_add_concat(self):
        pass


class TestCaseExpressions(BasicTestCase, unittest.TestCase):

    def test_ifelse(self):
        bools = self.table.g.isnull()
        result = bools.ifelse("foo", "bar")
        assert isinstance(result, ir.StringArray)

    def test_ifelse_literal(self):
        pass

    def test_simple_case_expr(self):
        case1, result1 = "foo", self.table.a
        case2, result2 = "bar", self.table.c
        default_result = self.table.b

        expr1 = self.table.g.lower().cases(
            [(case1, result1),
             (case2, result2)],
            default=default_result
        )

        expr2 = (self.table.g.lower().case()
                 .when(case1, result1)
                 .when(case2, result2)
                 .else_(default_result)
                 .end())

        assert_equal(expr1, expr2)
        assert isinstance(expr1, ir.Int32Array)

    def test_multiple_case_expr(self):
        case1 = self.table.a == 5
        case2 = self.table.b == 128
        case3 = self.table.c == 1000

        result1 = self.table.f
        result2 = self.table.b * 2
        result3 = self.table.e

        default = self.table.d

        expr = (ibis.case()
                .when(case1, result1)
                .when(case2, result2)
                .when(case3, result3)
                .else_(default)
                .end())

        op = expr.op()
        assert isinstance(expr, ir.DoubleArray)
        assert isinstance(op, ops.SearchedCase)
        assert op.default is default

    def test_simple_case_no_default(self):
        # TODO: this conflicts with the null else cases below. Make a decision
        # about what to do, what to make the default behavior based on what the
        # user provides. SQL behavior is to use NULL when nothing else
        # provided. The .replace convenience API could use the field values as
        # the default, getting us around this issue.
        pass

    def test_simple_case_null_else(self):
        expr = self.table.g.case().when("foo", "bar").end()
        op = expr.op()

        assert isinstance(expr, ir.StringArray)
        assert isinstance(op.default, ir.ValueExpr)
        assert isinstance(op.default.op(), ir.NullLiteral)

    def test_multiple_case_null_else(self):
        expr = ibis.case().when(self.table.g == "foo", "bar").end()
        op = expr.op()

        assert isinstance(expr, ir.StringArray)
        assert isinstance(op.default, ir.ValueExpr)
        assert isinstance(op.default.op(), ir.NullLiteral)

    def test_case_type_precedence(self):
        pass

    def test_no_implicit_cast_possible(self):
        pass


class TestExprList(unittest.TestCase):

    def setUp(self):
        exprs = [ibis.literal(1).name('a'),
                 ibis.literal(2).name('b')]

        self.expr = ibis.expr_list(exprs)

    def test_names(self):
        assert self.expr.names() == ['a', 'b']

    def test_prefix(self):
        prefixed = self.expr.prefix('foo_')
        result = prefixed.names()
        assert result == ['foo_a', 'foo_b']

    def test_rename(self):
        renamed = self.expr.rename(lambda x: 'foo({0})'.format(x))
        result = renamed.names()
        assert result == ['foo(a)', 'foo(b)']

    def test_suffix(self):
        suffixed = self.expr.suffix('.x')
        result = suffixed.names()
        assert result == ['a.x', 'b.x']

    def test_concat(self):
        exprs = [ibis.literal(1).name('a'),
                 ibis.literal(2).name('b')]

        exprs2 = [ibis.literal(3).name('c'),
                  ibis.literal(4).name('d')]

        list1 = ibis.expr_list(exprs)
        list2 = ibis.expr_list(exprs2)

        result = list1.concat(list2)
        expected = ibis.expr_list(exprs + exprs2)
        assert_equal(result, expected)
