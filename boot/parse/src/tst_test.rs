use super::*;
use crate::shred::ParsedTest;
use crate::token_cursor::TokenCursor;
use boot_db::ContentHash;
use boot_db::FileId;
use boot_db::Span;
use boot_db::SpannedTerm;
use boot_db::SpannedToken;
use boot_db::Term;
use boot_db::Token;
use boot_db::Value;
use boot_lex::lex_source;

#[test]
fn test_parse_test_block() {
  let source = "test 1 end-test";
  let ts = lex_source("test", source, ContentHash([0; 32])).unwrap();
  let tokens: Vec<&SpannedToken> = ts
    .tokens
    .iter()
    .filter(|t| !matches!(t.value, Token::Trivia(_)))
    .collect();
  let mut cursor =
    TokenCursor::new(FileId("test".to_string()), source.len(), &tokens);

  let item = parse_test(&mut cursor).unwrap();
  let expected_body = vec![SpannedTerm::new(
    Term::Literal(Value::Integer(1)),
    Span { start: 5, end: 6 },
  )];
  assert_eq!(
    item,
    ParsedTest {
      body: expected_body
    }
  );
}
