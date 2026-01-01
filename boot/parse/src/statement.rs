use crate::shred::ParsedStatement;
use crate::term::parse_term;
use crate::token_cursor::TokenCursor;
use crate::token_cursor::advance_token_cursor;
use boot_db::DiagnosticResult;
use boot_db::PunctuationTokenKind;
use boot_db::Token;

pub(crate) fn parse_statement(
  cursor: &mut TokenCursor<'_>,
) -> DiagnosticResult<ParsedStatement> {
  let term = parse_term(cursor)?;

  if let Some(t) = cursor.head {
    if t.value == Token::Punctuation(PunctuationTokenKind::Comma) {
      advance_token_cursor(cursor);
    }
  }

  Ok(ParsedStatement { term })
}

#[cfg(test)]
#[path = "statement_test.rs"]
mod statement_test;
