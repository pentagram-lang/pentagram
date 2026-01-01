use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use crate::char_cursor::char_cursor_slice;
use boot_db::LiteralTokenKind;
use boot_db::TokenKind;

pub(crate) fn lex_string(
  cursor: &mut CharCursor<'_>,
  start: usize,
) -> TokenKind {
  advance_char_cursor(cursor); // Consumes first '
  let mut opener_count = 1;
  while cursor.head == Some('\'') {
    opener_count += 1;
    advance_char_cursor(cursor);
  }

  let content_start = cursor.offset;

  while let Some(c) = cursor.head {
    if c == '\'' {
      let mut closer_count = 1;
      let closer_start = cursor.offset;
      advance_char_cursor(cursor);
      while cursor.head == Some('\'') {
        closer_count += 1;
        advance_char_cursor(cursor);
      }

      if closer_count == opener_count {
        let content = &cursor.input[content_start .. closer_start];
        return TokenKind::Literal(LiteralTokenKind::String(
          content.to_string(),
        ));
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
#[path = "string_test.rs"]
mod string_test;
