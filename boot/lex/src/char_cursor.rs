use std::str::Chars;

pub(crate) struct CharCursor<'a> {
  pub(crate) input: &'a str,
  pub(crate) chars: Chars<'a>,
  pub(crate) head: Option<char>,
  pub(crate) offset: usize,
}

impl<'a> CharCursor<'a> {
  pub(crate) fn new(input: &'a str) -> Self {
    let mut chars = input.chars();
    let head = chars.next();
    Self {
      input,
      chars,
      head,
      offset: 0,
    }
  }
}

pub(crate) fn advance_char_cursor(cursor: &mut CharCursor<'_>) {
  if let Some(c) = cursor.head {
    cursor.offset += c.len_utf8();
    cursor.head = cursor.chars.next();
  }
}

pub(crate) fn char_cursor_slice<'a>(
  cursor: &CharCursor<'a>,
  start: usize,
) -> &'a str {
  &cursor.input[start .. cursor.offset]
}
