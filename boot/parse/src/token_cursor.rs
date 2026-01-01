use boot_db::FileId;
use boot_db::SpannedToken;

pub(crate) struct TokenCursor<'a> {
  pub(crate) file_id: FileId,
  pub(crate) source_len: usize,
  pub(crate) tokens: &'a [&'a SpannedToken],
  pub(crate) head: Option<&'a SpannedToken>,
  pub(crate) index: usize,
}

impl<'a> TokenCursor<'a> {
  pub(crate) fn new(
    file_id: FileId,
    source_len: usize,
    tokens: &'a [&'a SpannedToken],
  ) -> Self {
    let head = tokens.first().copied();
    Self {
      file_id,
      source_len,
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
