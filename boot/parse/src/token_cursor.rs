use boot_db::Token;

pub(crate) struct TokenCursor<'a> {
  pub(crate) source: &'a str,
  pub(crate) tokens: &'a [&'a Token],
  pub(crate) head: Option<&'a Token>,
  pub(crate) index: usize,
}

impl<'a> TokenCursor<'a> {
  pub(crate) fn new(source: &'a str, tokens: &'a [&'a Token]) -> Self {
    let head = tokens.first().copied();
    Self {
      source,
      tokens,
      head,
      index: 0,
    }
  }
}

pub(crate) fn advance_token_cursor(cursor: &mut TokenCursor<'_>) {
  if cursor.head.is_some() {
    cursor.index += 1;
    cursor.head = cursor.tokens.get(cursor.index).copied();
  }
}

#[cfg(test)]
#[path = "token_cursor_test.rs"]
mod token_cursor_test;
