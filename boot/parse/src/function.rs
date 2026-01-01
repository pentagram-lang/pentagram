use crate::shred::ParsedFunction;
use crate::term::parse_term;
use crate::token_cursor::TokenCursor;
use crate::token_cursor::advance_token_cursor;
use boot_db::Diagnostic;
use boot_db::DiagnosticResult;
use boot_db::IdentifierTokenKind;
use boot_db::KeywordTokenKind;
use boot_db::PunctuationTokenKind;
use boot_db::TokenKind;

pub(crate) fn parse_function(
  cursor: &mut TokenCursor<'_>,
) -> DiagnosticResult<ParsedFunction> {
  advance_token_cursor(cursor); // eat 'def'

  let Some(token) = cursor.head else {
    return Err(Diagnostic {
      full_source: cursor.source.to_string(),
      error_offset: cursor.source.len(),
      error_message: "Unexpected end of input, expected function name"
        .to_string(),
    });
  };

  let name = match &token.kind {
    TokenKind::Identifier(IdentifierTokenKind::Word(s)) => {
      let name = s.clone();
      advance_token_cursor(cursor);
      name
    }
    _ => {
      return Err(Diagnostic {
        full_source: cursor.source.to_string(),
        error_offset: token.start,
        error_message: "expected function name".to_string(),
      });
    }
  };

  match cursor.head {
    Some(token)
      if matches!(
        token.kind,
        TokenKind::Keyword(KeywordTokenKind::Fn)
      ) =>
    {
      advance_token_cursor(cursor);
    }
    Some(token) => {
      return Err(Diagnostic {
        full_source: cursor.source.to_string(),
        error_offset: token.start,
        error_message: "expected 'fn'".to_string(),
      });
    }
    None => {
      return Err(Diagnostic {
        full_source: cursor.source.to_string(),
        error_offset: cursor.source.len(),
        error_message: "Unexpected end of input, expected 'fn'"
          .to_string(),
      });
    }
  }

  let mut body = Vec::new();
  while let Some(t) = cursor.head {
    if matches!(t.kind, TokenKind::Keyword(KeywordTokenKind::EndFn)) {
      break;
    }
    body.push(parse_term(cursor)?);

    if let Some(t) = cursor.head {
      if t.kind == TokenKind::Punctuation(PunctuationTokenKind::Comma) {
        advance_token_cursor(cursor);
      }
    }
  }

  match cursor.head {
    Some(t)
      if matches!(t.kind, TokenKind::Keyword(KeywordTokenKind::EndFn)) =>
    {
      advance_token_cursor(cursor);
    }
    Some(t) => {
      return Err(Diagnostic {
        full_source: cursor.source.to_string(),
        error_offset: t.start,
        error_message: "expected 'end-fn'".to_string(),
      });
    }
    None => {
      return Err(Diagnostic {
        full_source: cursor.source.to_string(),
        error_offset: cursor.source.len(),
        error_message: "Unexpected end of input, expected 'end-fn'"
          .to_string(),
      });
    }
  }

  if let Some(t) = cursor.head {
    if t.kind == TokenKind::Punctuation(PunctuationTokenKind::Comma) {
      advance_token_cursor(cursor);
    }
  }

  Ok(ParsedFunction { name, body })
}

#[cfg(test)]
#[path = "function_test.rs"]
mod function_test;
