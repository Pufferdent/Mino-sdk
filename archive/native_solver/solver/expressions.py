from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass


class Token:
    OR = "OR"
    AND = "AND"
    NOT = "NOT"
    AVOID = "AVOID"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    PIECE = "PIECE"
    REGEX = "REGEX"
    EOF = "EOF"


_TOKEN_SPEC = [
    (r"\|\|", Token.OR),
    (r"&&", Token.AND),
    (r"\!", Token.NOT),
    (r"\^", Token.AVOID),
    (r"\(", Token.LPAREN),
    (r"\)", Token.RPAREN),
    (r"/[^/]*/", Token.REGEX),
    (r"[TILJSZO]+", Token.PIECE),
    (r"\s+", None),
]


@dataclass(frozen=True)
class TokenInfo:
    type: str
    value: str
    pos: int


def _tokenize(expr: str) -> list[TokenInfo]:
    tokens: list[TokenInfo] = []
    pos = 0
    while pos < len(expr):
        match = None
        for pattern, tok_type in _TOKEN_SPEC:
            m = re.match(pattern, expr[pos:])
            if m:
                matched = m.group(0)
                if tok_type is not None:
                    tokens.append(TokenInfo(tok_type, matched, pos))
                pos += len(matched)
                match = m
                break
        if match is None:
            raise ValueError(f"Unexpected character at position {pos}: {expr[pos]!r}")
    tokens.append(TokenInfo(Token.EOF, "", pos))
    return tokens


class ASTNode(ABC):
    @abstractmethod
    def accept(self, visitor: "ASTVisitor") -> object:
        ...


@dataclass(frozen=True)
class Literal(ASTNode):
    pieces: str

    def accept(self, visitor: "ASTVisitor") -> object:
        return visitor.visit_literal(self)


@dataclass(frozen=True)
class RegexLiteral(ASTNode):
    pattern: str

    def accept(self, visitor: "ASTVisitor") -> object:
        return visitor.visit_regex(self)


@dataclass(frozen=True)
class Not(ASTNode):
    child: ASTNode

    def accept(self, visitor: "ASTVisitor") -> object:
        return visitor.visit_not(self)


@dataclass(frozen=True)
class Avoid(ASTNode):
    child: ASTNode

    def accept(self, visitor: "ASTVisitor") -> object:
        return visitor.visit_avoid(self)


@dataclass(frozen=True)
class And(ASTNode):
    left: ASTNode
    right: ASTNode

    def accept(self, visitor: "ASTVisitor") -> object:
        return visitor.visit_and(self)


@dataclass(frozen=True)
class Or(ASTNode):
    left: ASTNode
    right: ASTNode

    def accept(self, visitor: "ASTVisitor") -> object:
        return visitor.visit_or(self)


class ASTVisitor(ABC):
    @abstractmethod
    def visit_literal(self, node: Literal) -> object:
        ...

    @abstractmethod
    def visit_regex(self, node: RegexLiteral) -> object:
        ...

    @abstractmethod
    def visit_not(self, node: Not) -> object:
        ...

    @abstractmethod
    def visit_avoid(self, node: Avoid) -> object:
        ...

    @abstractmethod
    def visit_and(self, node: And) -> object:
        ...

    @abstractmethod
    def visit_or(self, node: Or) -> object:
        ...


class _Parser:
    def __init__(self, tokens: list[TokenInfo]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _current(self) -> TokenInfo:
        return self.tokens[self.pos]

    def _advance(self) -> TokenInfo:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, tok_type: str) -> TokenInfo:
        tok = self._advance()
        if tok.type != tok_type:
            raise ValueError(
                f"Expected {tok_type}, got {tok.type} ({tok.value!r}) at position {tok.pos}"
            )
        return tok

    def parse(self) -> ASTNode:
        node = self._parse_or()
        if self._current().type != Token.EOF:
            tok = self._current()
            raise ValueError(f"Unexpected token: {tok.type} ({tok.value!r}) at position {tok.pos}")
        return node

    def _parse_or(self) -> ASTNode:
        node = self._parse_and()
        while self._current().type == Token.OR:
            self._advance()
            node = Or(node, self._parse_and())
        return node

    def _parse_and(self) -> ASTNode:
        node = self._parse_unary()
        while self._current().type == Token.AND:
            self._advance()
            node = And(node, self._parse_unary())
        return node

    def _parse_unary(self) -> ASTNode:
        tok = self._current()
        if tok.type == Token.NOT:
            self._advance()
            return Not(self._parse_unary())
        if tok.type == Token.AVOID:
            self._advance()
            return Avoid(self._parse_unary())
        return self._parse_atomic()

    def _parse_atomic(self) -> ASTNode:
        tok = self._current()
        if tok.type == Token.PIECE:
            self._advance()
            return Literal(tok.value)
        if tok.type == Token.REGEX:
            self._advance()
            pattern = tok.value[1:-1]
            return RegexLiteral(pattern)
        if tok.type == Token.LPAREN:
            self._advance()
            node = self._parse_or()
            self._expect(Token.RPAREN)
            return node
        raise ValueError(f"Unexpected token: {tok.type} ({tok.value!r}) at position {tok.pos}")


def parse_expression(expr: str) -> ASTNode:
    tokens = _tokenize(expr)
    parser = _Parser(tokens)
    return parser.parse()


def evaluate_ast(node: ASTNode, saves: list[str]) -> bool:
    if isinstance(node, Literal):
        wanted = Counter(node.pieces)
        return any(not (wanted - Counter(save)) for save in saves)
    elif isinstance(node, RegexLiteral):
        try:
            pat = re.compile(node.pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex: '{node.pattern}' - {e}")
        return any(pat.search(save) for save in saves)
    elif isinstance(node, Not):
        return not evaluate_ast(node.child, saves)
    elif isinstance(node, Avoid):
        return any(
            not evaluate_ast(node.child, [save]) for save in saves
        )
    elif isinstance(node, And):
        left_val = evaluate_ast(node.left, saves)
        if not left_val:
            return False
        return evaluate_ast(node.right, saves)
    elif isinstance(node, Or):
        left_val = evaluate_ast(node.left, saves)
        if left_val:
            return True
        return evaluate_ast(node.right, saves)
    raise ValueError(f"Unknown AST node type: {type(node)}")


def _all_index(seq: list[bool]) -> list[int]:
    return [i for i, val in enumerate(seq) if val]


def evaluate_ast_all(node: ASTNode, saves: list[str]) -> list[int]:
    if isinstance(node, Literal):
        wanted = Counter(node.pieces)
        return _all_index(
            [not (wanted - Counter(save)) for save in saves]
        )
    elif isinstance(node, RegexLiteral):
        try:
            pat = re.compile(node.pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex: '{node.pattern}' - {e}")
        return _all_index([bool(pat.search(save)) for save in saves])
    elif isinstance(node, Not):
        child_result = evaluate_ast_all(node.child, saves)
        if len(child_result) > 0:
            return []
        return list(range(len(saves)))
    elif isinstance(node, Avoid):
        return _all_index(
            [
                not bool(evaluate_ast_all(node.child, [save]))
                for save in saves
            ]
        )
    elif isinstance(node, And):
        left_val = evaluate_ast_all(node.left, saves)
        if not left_val:
            return []
        return evaluate_ast_all(node.right, saves)
    elif isinstance(node, Or):
        left_val = evaluate_ast_all(node.left, saves)
        if left_val:
            return left_val
        return evaluate_ast_all(node.right, saves)
    raise ValueError(f"Unknown AST node type: {type(node)}")
