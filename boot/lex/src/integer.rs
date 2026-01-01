use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use crate::char_cursor::char_cursor_slice;
use boot_db::LiteralToken;
use boot_db::Token;

pub(crate) fn lex_integer(
  cursor: &mut CharCursor<'_>,
  start: usize,
) -> Token {
  lex_integer_impl(cursor, start, 1)
}

pub(crate) fn lex_integer_negative(
  cursor: &mut CharCursor<'_>,
  start: usize,
) -> Token {
  lex_integer_impl(cursor, start, -1)
}

fn lex_integer_impl(
  cursor: &mut CharCursor<'_>,
  start: usize,
  multiplier: i64,
) -> Token {
  let mut val: i64 = 0;

  while let Some(c) = cursor.head {
    if let Some(digit) = c.to_digit(10) {
      let digit = i64::from(digit) * multiplier;
      if let Some(new_val) =
        val.checked_mul(10).and_then(|v| v.checked_add(digit))
      {
        val = new_val;
      } else {
        while cursor.head.is_some_and(|c| c.is_ascii_digit()) {
          advance_char_cursor(cursor);
        }
        return Token::Unknown(
          char_cursor_slice(cursor, start).to_string(),
        );
      }
      advance_char_cursor(cursor);
    } else {
      break;
    }
  }

  Token::Literal(LiteralToken::Integer(val))
}

#[cfg(test)]
#[path = "integer_test.rs"]
mod integer_test;
