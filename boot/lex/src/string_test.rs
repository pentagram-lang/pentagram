use super::*;
use boot_db::LiteralTokenKind;

#[test]
fn test_lex_string() {
  let input = "'hello world' next";
  let mut cursor = CharCursor::new(input);
  let token = lex_string(&mut cursor, 0);
  assert_eq!(
    token,
    TokenKind::Literal(LiteralTokenKind::String(
      "hello world".to_string()
    ))
  );
}

#[test]
fn test_lex_string_triple() {
  let input = "'''hello ' world''' next";
  let mut cursor = CharCursor::new(input);
  let token = lex_string(&mut cursor, 0);
  assert_eq!(
    token,
    TokenKind::Literal(LiteralTokenKind::String(
      "hello ' world".to_string()
    ))
  );
}

#[test]
fn test_lex_string_mismatch_too_many_closers() {
  let input = "'hello'' next";
  let mut cursor = CharCursor::new(input);
  let token = lex_string(&mut cursor, 0);
  assert_eq!(token, TokenKind::Unknown("'hello''".to_string()));
}

#[test]
fn test_lex_unterminated_string() {
  let input = "'hello world";
  let mut cursor = CharCursor::new(input);
  let token = lex_string(&mut cursor, 0);
  assert_eq!(token, TokenKind::Unknown("'hello world".to_string()));
}
