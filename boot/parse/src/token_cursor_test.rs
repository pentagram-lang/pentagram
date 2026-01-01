use super::*;
use boot_db::ContentHash;
use boot_db::LiteralToken;
use boot_db::SpannedToken;
use boot_db::Token;
use boot_lex::lex_source;

#[test]
fn test_token_cursor_advance() {
  let source = "1 2";
  let ts = lex_source("test", source, ContentHash([0; 32])).unwrap();
  let tokens: Vec<&SpannedToken> = ts
    .tokens
    .iter()
    .filter(|t| !matches!(t.value, Token::Trivia(_)))
    .collect();

  let mut cursor =
    TokenCursor::new(FileId("test".to_string()), source.len(), &tokens);

  let t1 = cursor.head.unwrap();
  advance_token_cursor(&mut cursor);
  assert_eq!(t1.value, Token::Literal(LiteralToken::Integer(1)));

  let t2 = cursor.head.unwrap();
  advance_token_cursor(&mut cursor);
  assert_eq!(t2.value, Token::Literal(LiteralToken::Integer(2)));

  assert!(cursor.head.is_none());
}
