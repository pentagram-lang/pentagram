use super::*;
use boot_db::IdentifierToken;
use boot_db::KeywordToken;
use boot_db::LiteralToken;
use boot_db::PunctuationToken;

fn check(input: &str, expected: &[Token]) {
  let record = lex_source("test.penta", input, ContentHash([0; 32]))
    .expect("Failed to lex source");

  let actual: Vec<Token> =
    record.tokens.into_iter().map(|t| t.value).collect();
  let expected_vec: Vec<Token> = expected.to_vec();

  assert_eq!(actual, expected_vec, "Failed for input: '{input}'");
}

fn ident(s: &str) -> Token {
  Token::Identifier(IdentifierToken::Word(s.to_string()))
}

fn integer(i: i64) -> Token {
  Token::Literal(LiteralToken::Integer(i))
}

fn string(s: &str) -> Token {
  Token::Literal(LiteralToken::String(s.to_string()))
}

fn invalid_term() -> Token {
  Token::Trivia(TriviaToken::InvalidTermination)
}

fn unknown(s: &str) -> Token {
  Token::Unknown(s.to_string())
}

fn whitespace() -> Token {
  Token::Trivia(TriviaToken::Whitespace)
}

fn comma() -> Token {
  Token::Punctuation(PunctuationToken::Comma)
}

fn keyword(k: KeywordToken) -> Token {
  Token::Keyword(k)
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
      keyword(KeywordToken::Def),
      whitespace(),
      ident("foo"),
      whitespace(),
      keyword(KeywordToken::Fn),
      whitespace(),
      keyword(KeywordToken::EndFn),
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
      Token::Trivia(TriviaToken::Comment),
      invalid_term(),
      ident("bar"),
    ],
  );
}
