use super::*;
use boot_db::IdentifierTokenKind;
use boot_db::LiteralTokenKind;

fn check(input: &str, expected: &[TokenKind]) {
  let record = lex_source("test.penta", input, ContentHash([0; 32]))
    .expect("Failed to lex source");

  let actual: Vec<TokenKind> =
    record.tokens.into_iter().map(|t| t.kind).collect();
  let expected_vec: Vec<TokenKind> = expected.to_vec();

  assert_eq!(actual, expected_vec, "Failed for input: '{input}'");
}

fn ident(s: &str) -> TokenKind {
  TokenKind::Identifier(IdentifierTokenKind::Word(s.to_string()))
}

fn integer(i: i64) -> TokenKind {
  TokenKind::Literal(LiteralTokenKind::Integer(i))
}

fn string(s: &str) -> TokenKind {
  TokenKind::Literal(LiteralTokenKind::String(s.to_string()))
}

fn invalid_term() -> TokenKind {
  TokenKind::Trivia(TriviaTokenKind::InvalidTermination)
}

fn unknown(s: &str) -> TokenKind {
  TokenKind::Unknown(s.to_string())
}

fn whitespace() -> TokenKind {
  TokenKind::Trivia(TriviaTokenKind::Whitespace)
}

fn comma() -> TokenKind {
  TokenKind::Punctuation(boot_db::PunctuationTokenKind::Comma)
}

fn keyword(k: boot_db::KeywordTokenKind) -> TokenKind {
  TokenKind::Keyword(k)
}

#[test]
fn test_lex_basic_sequence() {
  check(
    "123 'hello' world",
    &[
      integer(123),
      whitespace(),
      string("hello"),
      whitespace(),
      ident("world"),
    ],
  );
}

#[test]
fn test_lex_function_def() {
  check(
    "def foo fn end-fn",
    &[
      keyword(boot_db::KeywordTokenKind::Def),
      whitespace(),
      ident("foo"),
      whitespace(),
      keyword(boot_db::KeywordTokenKind::Fn),
      whitespace(),
      keyword(boot_db::KeywordTokenKind::EndFn),
    ],
  );
}

#[test]
fn test_lex_mixed_values() {
  check(
    "a, 1, 'b'",
    &[
      ident("a"),
      comma(),
      whitespace(),
      integer(1),
      comma(),
      whitespace(),
      string("b"),
    ],
  );
}

#[test]
fn test_lex_termination_word_invalid() {
  check(
    "foo[bar]",
    &[
      ident("foo"),
      invalid_term(),
      unknown("["),
      invalid_term(),
      ident("bar"),
      invalid_term(),
      unknown("]"),
    ],
  );
}

#[test]
fn test_lex_termination_integer_invalid() {
  check("123a", &[integer(123), invalid_term(), ident("a")]);
}

#[test]
fn test_lex_termination_string_invalid() {
  check("'foo'bar", &[string("foo"), invalid_term(), ident("bar")]);
}

#[test]
fn test_lex_termination_valid_whitespace() {
  check("foo bar", &[ident("foo"), whitespace(), ident("bar")]);
}

#[test]
fn test_lex_termination_valid_comma() {
  check("foo,bar", &[ident("foo"), comma(), ident("bar")]);
}

#[test]
fn test_lex_termination_valid_eof() {
  check("foo", &[ident("foo")]);
}

#[test]
fn test_lex_termination_plus_invalid() {
  check("+[", &[ident("+"), invalid_term(), unknown("[")]);
}

#[test]
fn test_lex_termination_hyphen_invalid() {
  check("-[", &[ident("-"), invalid_term(), unknown("[")]);
}

#[test]
fn test_lex_termination_comment_invalid() {
  check(
    "-- foo --bar",
    &[
      TokenKind::Trivia(TriviaTokenKind::Comment),
      invalid_term(),
      ident("bar"),
    ],
  );
}
