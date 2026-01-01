use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use boot_db::TokenKind;
use boot_db::TriviaTokenKind;

pub(crate) fn lex_whitespace(cursor: &mut CharCursor<'_>) -> TokenKind {
  advance_char_cursor(cursor);
  while let Some(c) = cursor.head {
    if c.is_whitespace() {
      advance_char_cursor(cursor);
    } else {
      break;
    }
  }
  TokenKind::Trivia(TriviaTokenKind::Whitespace)
}

#[cfg(test)]
#[path = "whitespace_test.rs"]
mod whitespace_test;
