use super::*;
use boot_db::LiteralTokenKind;
use boot_db::Token;
use boot_db::TokenKind;
use boot_lex::lex_source;

#[test]
fn test_cursor_basics() {
  let source = "1 2";
  let ts =
    lex_source("test", source, boot_db::ContentHash([0; 32])).unwrap();
  let tokens: Vec<&Token> = ts
    .tokens
    .iter()
    .filter(|t| !matches!(t.kind, TokenKind::Trivia(_)))
    .collect();

  let mut cursor = TokenCursor::new(source, &tokens);

  assert!(cursor.head.is_some());
  let t1 = cursor.head.unwrap();
  advance_token_cursor(&mut cursor);
  assert_eq!(t1.kind, TokenKind::Literal(LiteralTokenKind::Integer(1)));

  assert!(cursor.head.is_some());
  let t2 = cursor.head.unwrap();
  advance_token_cursor(&mut cursor);
  assert_eq!(t2.kind, TokenKind::Literal(LiteralTokenKind::Integer(2)));

  assert!(cursor.head.is_none());
  advance_token_cursor(&mut cursor);
  assert!(cursor.head.is_none());
}
