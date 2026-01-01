use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use crate::char_cursor::char_cursor_slice;
use boot_db::IdentifierTokenKind;
use boot_db::KeywordTokenKind;
use boot_db::Token;

pub(crate) fn lex_word(
  cursor: &mut CharCursor<'_>,
  start: usize,
  head: char,
) -> Token {
  let mut state = WordState::default();
  process_char(&mut state, head);
  advance_char_cursor(cursor);

  if state.is_invalid {
    return Token::Unknown(char_cursor_slice(cursor, start).to_string());
  }

  lex_word_impl(cursor, start, state)
}

pub(crate) fn lex_word_hyphen_prefix(
  cursor: &mut CharCursor<'_>,
  start: usize,
) -> Token {
  let mut state = WordState::default();
  process_char(&mut state, '-');
  lex_word_impl(cursor, start, state)
}

pub(crate) fn lex_word_plus_prefix(
  cursor: &mut CharCursor<'_>,
  start: usize,
) -> Token {
  let mut state = WordState::default();
  process_char(&mut state, '+');
  lex_word_impl(cursor, start, state)
}

fn lex_word_impl(
  cursor: &mut CharCursor<'_>,
  start: usize,
  mut state: WordState,
) -> Token {
  while let Some(c) = cursor.head {
    if !c.is_alphanumeric() && c != '-' && c != '_' {
      break;
    }
    process_char(&mut state, c);
    advance_char_cursor(cursor);
  }

  let word = char_cursor_slice(cursor, start);
  if state.is_invalid || state.first_char.is_none() {
    return Token::Unknown(word.to_string());
  }

  match word {
    "def" => Token::Keyword(KeywordTokenKind::Def),
    "fn" => Token::Keyword(KeywordTokenKind::Fn),
    "end-fn" => Token::Keyword(KeywordTokenKind::EndFn),
    "test" => Token::Keyword(KeywordTokenKind::Test),
    "end-test" => Token::Keyword(KeywordTokenKind::EndTest),
    _ => Token::Identifier(IdentifierTokenKind::Word(word.to_string())),
  }
}

#[derive(Default)]
struct WordState {
  is_invalid: bool,
  first_char: Option<char>,
  last_was_hyphen: bool,
}

fn process_char(state: &mut WordState, c: char) {
  if state.first_char.is_none() {
    state.first_char = Some(c);
    if !c.is_alphabetic()
      && c != '*'
      && c != '/'
      && c != '+'
      && c != '-'
      && c != '_'
    {
      state.is_invalid = true;
    }
  } else {
    if matches!(state.first_char, Some('*' | '/' | '+' | '-')) {
      state.is_invalid = true;
    }
    if c == '-' {
      if state.last_was_hyphen {
        state.is_invalid = true;
      }
      state.last_was_hyphen = true;
    } else if c == '_' || c.is_alphanumeric() {
      state.last_was_hyphen = false;
    } else {
      state.is_invalid = true;
    }
  }
}

#[cfg(test)]
#[path = "word_test.rs"]
mod word_test;
