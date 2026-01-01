use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use boot_db::Token;
use boot_db::TriviaToken;

pub(crate) fn lex_whitespace(cursor: &mut CharCursor<'_>) -> Token {
  advance_char_cursor(cursor);
  while let Some(c) = cursor.head {
    if c.is_whitespace() {
      advance_char_cursor(cursor);
    } else {
      break;
    }
  }
  Token::Trivia(TriviaToken::Whitespace)
}

#[cfg(test)]
#[path = "whitespace_test.rs"]
mod whitespace_test;
