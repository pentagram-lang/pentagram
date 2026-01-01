use super::*;
use boot_db::IdentifierTokenKind;
use boot_db::KeywordTokenKind;

fn ident(s: &str) -> Token {
  Token::Identifier(IdentifierTokenKind::Word(s.to_string()))
}

fn unknown(s: &str) -> Token {
  Token::Unknown(s.to_string())
}

fn check(input: &str, expected: &Token) {
  let mut cursor = CharCursor::new(input);
  let token = if input.starts_with('-')
    && !input.starts_with("--")
    && !input
      .get(1 .. 2)
      .is_some_and(|s| s.chars().next().unwrap().is_ascii_digit())
  {
    advance_char_cursor(&mut cursor);
    lex_word_hyphen_prefix(&mut cursor, 0)
  } else {
    let head = cursor.head.unwrap();
    lex_word(&mut cursor, 0, head)
  };
  assert_eq!(&token, expected, "Failed for input: '{input}'");
}

#[test]
fn test_lex_keyword_def() {
  check("def", &Token::Keyword(KeywordTokenKind::Def));
}

#[test]
fn test_lex_identifier() {
  check("hello-world", &ident("hello-world"));
}

#[test]
fn test_lex_minus_word() {
  check("-", &ident("-"));
}

#[test]
fn test_lex_invalid_minus_word() {
  check("-abc", &unknown("-abc"));
}

#[test]
fn test_lex_plus_word() {
  check("+", &ident("+"));
}

#[test]
fn test_lex_invalid_plus_word() {
  check("+abc", &unknown("+abc"));
}

#[test]
fn test_lex_double_hyphen_invalid() {
  check("foo--bar", &unknown("foo--bar"));
}

#[test]
fn test_lex_start_with_underscore_valid() {
  check("_foo", &ident("_foo"));
}

#[test]
fn test_lex_word_with_underscore() {
  check("foo_bar", &ident("foo_bar"));
}

#[test]
fn test_lex_unicode_word() {
  check("π", &ident("π"));
}

#[test]
fn test_lex_word_stops_at_unknown() {
  check("foo[bar]", &ident("foo"));
}
