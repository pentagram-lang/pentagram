use crate::token_cursor::TokenCursor;
use crate::token_cursor::advance_token_cursor;
use boot_db::Diagnostic;
use boot_db::DiagnosticResult;
use boot_db::IdentifierTokenKind;
use boot_db::LiteralTokenKind;
use boot_db::Term;
use boot_db::TokenKind;
use boot_db::Value;

pub(crate) fn parse_term(
  cursor: &mut TokenCursor<'_>,
) -> DiagnosticResult<Term> {
  let Some(token) = cursor.head else {
    return Err(Diagnostic {
      full_source: cursor.source.to_string(),
      error_offset: cursor.source.len(),
      error_message: "Unexpected end of input, expected term".to_string(),
    });
  };
  advance_token_cursor(cursor);

  match &token.kind {
    TokenKind::Literal(LiteralTokenKind::Integer(i)) => {
      Ok(Term::Literal(Value::Integer(*i)))
    }
    TokenKind::Literal(LiteralTokenKind::String(s)) => {
      Ok(Term::Literal(Value::String(s.clone())))
    }
    TokenKind::Identifier(IdentifierTokenKind::Word(s)) => {
      Ok(Term::Word(s.clone()))
    }
    TokenKind::Unknown(c) => Err(Diagnostic {
      full_source: cursor.source.to_string(),
      error_offset: token.start,
      error_message: format!("Unexpected character: {c}"),
    }),
    _ => Err(Diagnostic {
      full_source: cursor.source.to_string(),
      error_offset: token.start,
      error_message: "expected term".to_string(),
    }),
  }
}

#[cfg(test)]
#[path = "term_test.rs"]
mod term_test;
