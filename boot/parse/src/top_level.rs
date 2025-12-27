use crate::function::parse_function;
use crate::shred::TopLevelItem;
use crate::statement::parse_statement;
use crate::token_cursor::TokenCursor;
use crate::tst::parse_test;
use boot_db::Diagnostic;
use boot_db::DiagnosticResult;
use boot_db::KeywordTokenKind;
use boot_db::TokenKind;

pub(crate) fn parse_top_level_item(
  cursor: &mut TokenCursor<'_>,
) -> DiagnosticResult<TopLevelItem> {
  match cursor.head {
    Some(token) => match &token.kind {
      TokenKind::Keyword(KeywordTokenKind::Def) => {
        Ok(TopLevelItem::Function(parse_function(cursor)?))
      }
      TokenKind::Keyword(KeywordTokenKind::Test) => {
        Ok(TopLevelItem::Test(parse_test(cursor)?))
      }
      _ => Ok(TopLevelItem::Statement(parse_statement(cursor)?)),
    },
    None => Err(Diagnostic {
      full_source: cursor.source.to_string(),
      error_offset: cursor.source.len(),
      error_message: "Unexpected end of input".to_string(),
    }),
  }
}

#[cfg(test)]
#[path = "top_level_test.rs"]
mod top_level_test;
