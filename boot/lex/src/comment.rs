use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use crate::char_cursor::char_cursor_slice;
use boot_db::TokenKind;
use boot_db::TriviaTokenKind;

pub(crate) fn lex_comment(
  cursor: &mut CharCursor<'_>,
  start: usize,
) -> TokenKind {
  let mut opener_count = 2; // Two '-' already advanced in lex_source
  while cursor.head == Some('-') {
    opener_count += 1;
    advance_char_cursor(cursor);
  }

  while let Some(c) = cursor.head {
    if c == '-' {
      let mut closer_count = 1;
      advance_char_cursor(cursor);
      while cursor.head == Some('-') {
        closer_count += 1;
        advance_char_cursor(cursor);
      }

      if closer_count == opener_count {
        return TokenKind::Trivia(TriviaTokenKind::Comment);
      }

      if closer_count > opener_count {
        return TokenKind::Unknown(
          char_cursor_slice(cursor, start).to_string(),
        );
      }
    } else {
      advance_char_cursor(cursor);
    }
  }

  TokenKind::Unknown(char_cursor_slice(cursor, start).to_string())
}

#[cfg(test)]
#[path = "comment_test.rs"]
mod comment_test;
