use super::*;
use crate::char_cursor::CharCursor;
use boot_db::TriviaTokenKind;

#[test]
fn test_lex_whitespace() {
  let input = "   \t\n  next";
  let mut cursor = CharCursor::new(input);
  let token = lex_whitespace(&mut cursor);
  assert_eq!(token, Token::Trivia(TriviaTokenKind::Whitespace));

  assert_eq!(cursor.head, Some('n'));
}

#[test]
fn test_lex_single_whitespace() {
  let input = " next";
  let mut cursor = CharCursor::new(input);
  let token = lex_whitespace(&mut cursor);
  assert_eq!(token, Token::Trivia(TriviaTokenKind::Whitespace));

  assert_eq!(cursor.head, Some('n'));
}
