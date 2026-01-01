use crate::shred::ParsedTest;
use crate::term::parse_term;
use crate::token_cursor::TokenCursor;
use crate::token_cursor::advance_token_cursor;
use boot_db::Diagnostic;
use boot_db::DiagnosticResult;
use boot_db::KeywordTokenKind;
use boot_db::PunctuationTokenKind;
use boot_db::Span;
use boot_db::Token;

pub(crate) fn parse_test(
  cursor: &mut TokenCursor<'_>,
) -> DiagnosticResult<ParsedTest> {
  advance_token_cursor(cursor); // eat 'test'

  let mut body = Vec::new();
  while let Some(t) = cursor.head {
    if matches!(t.value, Token::Keyword(KeywordTokenKind::EndTest)) {
      break;
    }
    body.push(parse_term(cursor)?);

    if let Some(t) = cursor.head {
      if t.value == Token::Punctuation(PunctuationTokenKind::Comma) {
        advance_token_cursor(cursor);
      }
    }
  }

  match cursor.head {
    Some(t)
      if matches!(t.value, Token::Keyword(KeywordTokenKind::EndTest)) =>
    {
      advance_token_cursor(cursor);
    }
    Some(t) => {
      return Err(Diagnostic {
        file_id: cursor.file_id.clone(),
        span: t.span,
        error_message: "expected 'end-test'".to_string(),
      });
    }
    None => {
      return Err(Diagnostic {
        file_id: cursor.file_id.clone(),
        span: Span {
          start: cursor.source_len,
          end: cursor.source_len,
        },
        error_message: "Unexpected end of input, expected 'end-test'"
          .to_string(),
      });
    }
  }

  if let Some(t) = cursor.head {
    if t.value == Token::Punctuation(PunctuationTokenKind::Comma) {
      advance_token_cursor(cursor);
    }
  }

  Ok(ParsedTest { body })
}

#[cfg(test)]
#[path = "tst_test.rs"]
mod tst_test;
