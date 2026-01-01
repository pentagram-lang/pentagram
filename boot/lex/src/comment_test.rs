use super::*;
use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use boot_db::TriviaTokenKind;

#[test]
fn test_lex_comment_simple() {
  let input = "-- hello -- next";
  let mut cursor = CharCursor::new(input);
  advance_char_cursor(&mut cursor);
  advance_char_cursor(&mut cursor);
  let token = lex_comment(&mut cursor, 0);
  assert_eq!(token, Token::Trivia(TriviaTokenKind::Comment));
  assert_eq!(cursor.head, Some(' '));
}

#[test]
fn test_lex_comment_multiline() {
  let input = "--\n line 1\n line 2\n-- next";
  let mut cursor = CharCursor::new(input);
  advance_char_cursor(&mut cursor);
  advance_char_cursor(&mut cursor);
  let token = lex_comment(&mut cursor, 0);
  assert_eq!(token, Token::Trivia(TriviaTokenKind::Comment));
  assert_eq!(cursor.head, Some(' '));
}

#[test]
fn test_lex_comment_nested_style() {
  let input = "--- outer -- inner -- outer --- next";
  let mut cursor = CharCursor::new(input);
  advance_char_cursor(&mut cursor);
  advance_char_cursor(&mut cursor);
  let token = lex_comment(&mut cursor, 0);
  assert_eq!(token, Token::Trivia(TriviaTokenKind::Comment));
  assert_eq!(cursor.head, Some(' '));
}

#[test]
fn test_lex_comment_mismatch_too_many_closers() {
  let input = "-- hello --- next";
  let mut cursor = CharCursor::new(input);
  advance_char_cursor(&mut cursor);
  advance_char_cursor(&mut cursor);
  let token = lex_comment(&mut cursor, 0);
  assert_eq!(token, Token::Unknown("-- hello ---".to_string()));
}

#[test]
fn test_lex_comment_mismatch_too_few_closers() {
  let input = "--- hello -- next";
  let mut cursor = CharCursor::new(input);
  advance_char_cursor(&mut cursor);
  advance_char_cursor(&mut cursor);
  let token = lex_comment(&mut cursor, 0);
  assert_eq!(token, Token::Unknown("--- hello -- next".to_string()));
}
