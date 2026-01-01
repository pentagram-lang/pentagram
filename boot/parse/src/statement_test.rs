use super::*;
use crate::shred::ParsedStatement;
use crate::token_cursor::TokenCursor;
use boot_db::Span;
use boot_db::SpannedTerm;
use boot_db::SpannedToken;
use boot_db::Term;
use boot_db::Token;
use boot_db::Value;
use boot_lex::lex_source;

#[test]
fn test_parse_statement() {
  let source = "123,";
  let ts =
    lex_source("test", source, boot_db::ContentHash([0; 32])).unwrap();
  let tokens: Vec<&SpannedToken> = ts
    .tokens
    .iter()
    .filter(|t| !matches!(t.value, Token::Trivia(_)))
    .collect();
  let mut cursor = TokenCursor::new(
    boot_db::FileId("test".to_string()),
    source.len(),
    &tokens,
  );

  let item = parse_statement(&mut cursor).unwrap();
  assert_eq!(
    item,
    ParsedStatement {
      term: SpannedTerm::new(
        Term::Literal(Value::Integer(123)),
        Span { start: 0, end: 3 }
      )
    }
  );
}
