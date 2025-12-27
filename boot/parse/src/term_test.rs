use super::*;
use crate::token_cursor::TokenCursor;
use boot_db::Token;
use boot_lex::lex_source;

#[test]
fn test_parse_term_integer() {
  let source = "123";
  let ts =
    lex_source("test", source, boot_db::ContentHash([0; 32])).unwrap();
  let tokens: Vec<&Token> = ts.tokens.iter().collect();
  let mut cursor = TokenCursor::new(source, &tokens);

  let term = parse_term(&mut cursor).unwrap();
  assert_eq!(term, Term::Literal(Value::Integer(123)));
}

#[test]
fn test_parse_term_string() {
  let source = "'hello'";
  let ts =
    lex_source("test", source, boot_db::ContentHash([0; 32])).unwrap();
  let tokens: Vec<&Token> = ts.tokens.iter().collect();
  let mut cursor = TokenCursor::new(source, &tokens);

  let term = parse_term(&mut cursor).unwrap();
  assert_eq!(term, Term::Literal(Value::String("hello".to_string())));
}

#[test]
fn test_parse_term_word() {
  let source = "abc";
  let ts =
    lex_source("test", source, boot_db::ContentHash([0; 32])).unwrap();
  let tokens: Vec<&Token> = ts.tokens.iter().collect();
  let mut cursor = TokenCursor::new(source, &tokens);

  let term = parse_term(&mut cursor).unwrap();
  assert_eq!(term, Term::Word("abc".to_string()));
}
