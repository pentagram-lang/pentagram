use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use boot_db::PunctuationToken;
use boot_db::Token;

pub(crate) fn lex_punctuation(cursor: &mut CharCursor<'_>) -> Token {
  advance_char_cursor(cursor);
  Token::Punctuation(PunctuationToken::Comma)
}

#[cfg(test)]
#[path = "punctuation_test.rs"]
mod punctuation_test;
