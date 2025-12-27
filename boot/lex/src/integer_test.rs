use super::*;
use boot_db::LiteralTokenKind;

fn unknown(s: &str) -> TokenKind {
  TokenKind::Unknown(s.to_string())
}

#[test]
fn test_lex_integer() {
  let input = "12345 next";
  let mut cursor = CharCursor::new(input);
  let token = lex_integer(&mut cursor, 0);
  assert_eq!(token, TokenKind::Literal(LiteralTokenKind::Integer(12345)));
}

#[test]
fn test_lex_plus_integer() {
  let input = "+12345 next";
  let mut cursor = CharCursor::new(input);
  advance_char_cursor(&mut cursor);
  let token = lex_integer(&mut cursor, 0);
  assert_eq!(token, TokenKind::Literal(LiteralTokenKind::Integer(12345)));
}

#[test]
fn test_lex_negative_integer() {
  let input = "-12345 next";
  let mut cursor = CharCursor::new(input);
  advance_char_cursor(&mut cursor);
  let token = lex_integer_negative(&mut cursor, 0);
  assert_eq!(token, TokenKind::Literal(LiteralTokenKind::Integer(-12345)));
}

#[test]
fn test_lex_integer_min() {
  let input = "-9223372036854775808";
  let mut cursor = CharCursor::new(input);
  advance_char_cursor(&mut cursor);
  let token = lex_integer_negative(&mut cursor, 0);
  assert_eq!(
    token,
    TokenKind::Literal(LiteralTokenKind::Integer(i64::MIN))
  );
}

#[test]
fn test_lex_integer_overflow() {
  let input = "9223372036854775808";
  let mut cursor = CharCursor::new(input);
  let token = lex_integer(&mut cursor, 0);
  assert_eq!(token, unknown("9223372036854775808"));
}
