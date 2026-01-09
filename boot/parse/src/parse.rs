use crate::shred::ParsedModule;
use crate::shred::shred_items;
use crate::token_cursor::TokenCursor;
use crate::top_level::parse_top_level_item;
use boot_db::DiagnosticResult;
use boot_db::SpannedToken;
use boot_db::Token;
use boot_db::TokenStreamRecord;
use boot_db::TriviaTokenKind;

pub fn parse_source(
  path: &str,
  source: &str,
  token_stream: &TokenStreamRecord,
) -> DiagnosticResult<ParsedModule> {
  let tokens: Vec<&SpannedToken> = token_stream
    .tokens
    .iter()
    .filter(|t| {
      !matches!(
        t.value,
        Token::Trivia(
          TriviaTokenKind::Whitespace | TriviaTokenKind::Comment
        )
      )
    })
    .collect();

  let mut cursor =
    TokenCursor::new(token_stream.file_id.clone(), source.len(), &tokens);
  let mut items = Vec::new();

  while cursor.head.is_some() {
    items.push(parse_top_level_item(&mut cursor)?);
  }

  Ok(shred_items(path, items))
}

#[cfg(test)]
#[path = "parse_test.rs"]
mod parse_test;
