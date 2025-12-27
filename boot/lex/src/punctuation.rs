use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use boot_db::PunctuationTokenKind;
use boot_db::TokenKind;

pub(crate) fn lex_punctuation(cursor: &mut CharCursor<'_>) -> TokenKind {
  advance_char_cursor(cursor);
  TokenKind::Punctuation(PunctuationTokenKind::Comma)
}

#[cfg(test)]
#[path = "punctuation_test.rs"]
mod punctuation_test;
