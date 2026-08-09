import pytest
from tetris_sdk.solver.expressions import (
    parse_expression,
    evaluate_ast,
    evaluate_ast_all,
    Literal,
    RegexLiteral,
    Not,
    Avoid,
    And,
    Or,
)


class TestParseExpression:
    def test_simple_piece_literal(self):
        ast = parse_expression("T")
        assert isinstance(ast, Literal)
        assert ast.pieces == "T"

    def test_and_expression(self):
        ast = parse_expression("T&&S")
        assert isinstance(ast, And)
        assert isinstance(ast.left, Literal)
        assert isinstance(ast.right, Literal)

    def test_or_expression(self):
        ast = parse_expression("T||S")
        assert isinstance(ast, Or)

    def test_not_expression(self):
        ast = parse_expression("!T")
        assert isinstance(ast, Not)
        assert isinstance(ast.child, Literal)

    def test_avoid_expression(self):
        ast = parse_expression("^S")
        assert isinstance(ast, Avoid)

    def test_nested_expression(self):
        ast = parse_expression("!(T&&S)||L")
        assert isinstance(ast, Or)
        assert isinstance(ast.left, Not)

    def test_regex_expression(self):
        ast = parse_expression("/T[ISZO]/")
        assert isinstance(ast, RegexLiteral)
        assert ast.pattern == "T[ISZO]"

    def test_multi_char_literal(self):
        ast = parse_expression("TSZ")
        assert isinstance(ast, Literal)
        assert ast.pieces == "TSZ"

    def test_precedence_and_before_or(self):
        ast = parse_expression("T&&S||L")
        assert isinstance(ast, Or)
        assert isinstance(ast.left, And)

    def test_precedence_not_before_and(self):
        ast = parse_expression("!T&&S")
        assert isinstance(ast, And)
        assert isinstance(ast.left, Not)

    def test_whitespace_handling(self):
        ast1 = parse_expression("T && S || L")
        ast2 = parse_expression("T&&S||L")
        assert type(ast1) == type(ast2)

    def test_parenthesized(self):
        ast = parse_expression("(T)")
        assert isinstance(ast, Literal)

    def test_invalid_expression_missing_operand(self):
        with pytest.raises(ValueError):
            parse_expression("T&&")

    def test_invalid_character(self):
        with pytest.raises(ValueError):
            parse_expression("T&")


class TestEvaluateAST:
    def test_piece_literal_match(self):
        ast = parse_expression("T")
        assert evaluate_ast(ast, ["TI", "SZ"]) is True

    def test_piece_literal_no_match(self):
        ast = parse_expression("T")
        assert evaluate_ast(ast, ["LI", "SZ"]) is False

    def test_and_both_true(self):
        ast = parse_expression("T&&S")
        assert evaluate_ast(ast, ["TI", "SZ"]) is True

    def test_and_one_false(self):
        ast = parse_expression("T&&S")
        assert evaluate_ast(ast, ["TI", "LZ"]) is False

    def test_or_either(self):
        ast = parse_expression("T||S")
        assert evaluate_ast(ast, ["LI", "SZ"]) is True

    def test_not_inverts(self):
        ast = parse_expression("!T")
        assert evaluate_ast(ast, ["LI", "SZ"]) is True

    def test_not_inverts_false(self):
        ast = parse_expression("!T")
        assert evaluate_ast(ast, ["TI", "SZ"]) is False

    def test_avoid_possible(self):
        ast = parse_expression("^S")
        assert evaluate_ast(ast, ["TI", "LZ"]) is True

    def test_avoid_impossible(self):
        ast = parse_expression("^S")
        assert evaluate_ast(ast, ["TS", "SZ"]) is False

    def test_regex_match(self):
        ast = parse_expression("/T./")
        assert evaluate_ast(ast, ["TI", "SZ"]) is True

    def test_regex_no_match(self):
        ast = parse_expression("/^L/")
        assert evaluate_ast(ast, ["TI", "SZ"]) is False

    def test_queue_all_appear_in_same_save(self):
        ast = parse_expression("TSZ")
        assert evaluate_ast(ast, ["TSZ"]) is True

    def test_queue_not_all_in_same_save(self):
        ast = parse_expression("TSZ")
        assert evaluate_ast(ast, ["TI", "SZ"]) is False

    def test_queue_cross_saves(self):
        ast = parse_expression("T&&S&&Z")
        assert evaluate_ast(ast, ["TI", "SZ"]) is True

    def test_empty_saves(self):
        ast = parse_expression("T")
        assert evaluate_ast(ast, []) is False

    def test_complex_expression(self):
        ast = parse_expression("!(T&&S)||L")
        assert evaluate_ast(ast, ["TI", "LZ"]) is True

    def test_evaluate_ast_all(self):
        ast = parse_expression("T")
        result = evaluate_ast_all(ast, ["TI", "SZ"])
        assert result == [0]

    def test_evaluate_ast_all_no_match(self):
        ast = parse_expression("T")
        result = evaluate_ast_all(ast, ["LI", "SZ"])
        assert result == []
