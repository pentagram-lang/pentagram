use super::*;
use crate::shred::ParsedFunction;
use crate::shred::ParsedStatement;
use crate::token_cursor::TokenCursor;
use boot_db::Term;
use boot_db::Token;
use boot_db::Value;
use boot_lex::lex_source;

#[test]
fn test_parse_top_level_def() {
  let source = "def main fn end-fn";
  let ts =
    lex_source("test", source, boot_db::ContentHash([0; 32])).unwrap();
  let tokens: Vec<&Token> = ts
    .tokens
    .iter()
    .filter(|t| !matches!(t.kind, TokenKind::Trivia(_)))
    .collect();
  let mut cursor = TokenCursor::new(source, &tokens);

  let item = parse_top_level_item(&mut cursor).unwrap();
  let expected = TopLevelItem::Function(ParsedFunction {
    name: "main".to_string(),
    body: vec![],
  });
  assert_eq!(item, expected);
}

#[test]
fn test_parse_top_level_expr() {
  let source = "123";
  let ts =
    lex_source("test", source, boot_db::ContentHash([0; 32])).unwrap();
  let tokens: Vec<&Token> = ts
    .tokens
    .iter()
    .filter(|t| !matches!(t.kind, TokenKind::Trivia(_)))
    .collect();
  let mut cursor = TokenCursor::new(source, &tokens);

  let item = parse_top_level_item(&mut cursor).unwrap();
  assert_eq!(
    item,
    TopLevelItem::Statement(ParsedStatement {
      term: Term::Literal(Value::Integer(123))
    })
  );
}
