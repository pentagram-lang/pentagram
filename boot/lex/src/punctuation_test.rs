use super::*;
use crate::char_cursor::CharCursor;
use boot_db::PunctuationTokenKind;

#[test]
fn test_lex_punctuation_comma() {
  let mut cursor = CharCursor::new(",");
  let token = lex_punctuation(&mut cursor);
  assert_eq!(token, Token::Punctuation(PunctuationTokenKind::Comma));
  assert_eq!(cursor.offset, 1);
}
