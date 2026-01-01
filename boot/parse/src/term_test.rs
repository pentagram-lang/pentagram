use super::*;
use crate::token_cursor::TokenCursor;
use boot_db::ContentHash;
use boot_db::FileId;
use boot_db::Span;
use boot_db::SpannedTerm;
use boot_db::SpannedToken;
use boot_db::Term;
use boot_db::Value;
use boot_lex::lex_source;

#[test]
fn test_parse_term_integer() {
  let source = "123";
  let ts = lex_source("test", source, ContentHash([0; 32])).unwrap();
  let tokens: Vec<&SpannedToken> = ts.tokens.iter().collect();
  let mut cursor =
    TokenCursor::new(FileId("test".to_string()), source.len(), &tokens);

  let term = parse_term(&mut cursor).unwrap();
  assert_eq!(
    term,
    SpannedTerm::new(
      Term::Literal(Value::Integer(123)),
      Span { start: 0, end: 3 }
    )
  );
}

#[test]
fn test_parse_term_string() {
  let source = "'hello'";
  let ts = lex_source("test", source, ContentHash([0; 32])).unwrap();
  let tokens: Vec<&SpannedToken> = ts.tokens.iter().collect();
  let mut cursor =
    TokenCursor::new(FileId("test".to_string()), source.len(), &tokens);

  let term = parse_term(&mut cursor).unwrap();
  assert_eq!(
    term,
    SpannedTerm::new(
      Term::Literal(Value::String("hello".to_string())),
      Span { start: 0, end: 7 }
    )
  );
}

#[test]
fn test_parse_term_word() {
  let source = "abc";
  let ts = lex_source("test", source, ContentHash([0; 32])).unwrap();
  let tokens: Vec<&SpannedToken> = ts.tokens.iter().collect();
  let mut cursor =
    TokenCursor::new(FileId("test".to_string()), source.len(), &tokens);

  let term = parse_term(&mut cursor).unwrap();
  assert_eq!(
    term,
    SpannedTerm::new(
      Term::Word("abc".to_string()),
      Span { start: 0, end: 3 }
    )
  );
}
