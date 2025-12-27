use super::*;
use crate::shred::ParsedFunction;
use crate::token_cursor::TokenCursor;
use boot_db::Term;
use boot_db::Token;
use boot_db::Value;
use boot_lex::lex_source;

#[test]
fn test_parse_function() {
  let source = "def main fn 1 end-fn";
  let ts =
    lex_source("test", source, boot_db::ContentHash([0; 32])).unwrap();
  let tokens: Vec<&Token> = ts
    .tokens
    .iter()
    .filter(|t| !matches!(t.kind, TokenKind::Trivia(_)))
    .collect();
  let mut cursor = TokenCursor::new(source, &tokens);

  let item = parse_function(&mut cursor).unwrap();
  let expected_body = vec![Term::Literal(Value::Integer(1))];
  assert_eq!(
    item,
    ParsedFunction {
      name: "main".to_string(),
      body: expected_body
    }
  );
}
