use crate::token_cursor::TokenCursor;
use crate::token_cursor::advance_token_cursor;
use boot_db::Diagnostic;
use boot_db::DiagnosticResult;
use boot_db::IdentifierTokenKind;
use boot_db::LiteralTokenKind;
use boot_db::Spanned;
use boot_db::Term;
use boot_db::Token;
use boot_db::Value;

pub(crate) fn parse_term(
  cursor: &mut TokenCursor<'_>,
) -> DiagnosticResult<Spanned<Term>> {
  let Some(token) = cursor.head else {
    return Err(Diagnostic {
      full_source: cursor.source.to_string(),
      error_offset: cursor.source.len(),
      error_message: "Unexpected end of input, expected term".to_string(),
    });
  };
  advance_token_cursor(cursor);

  let span = token.span;
  match &token.value {
    Token::Literal(LiteralTokenKind::Integer(i)) => {
      Ok(Spanned::new(Term::Literal(Value::Integer(*i)), span))
    }
    Token::Literal(LiteralTokenKind::String(s)) => {
      Ok(Spanned::new(Term::Literal(Value::String(s.clone())), span))
    }
    Token::Identifier(IdentifierTokenKind::Word(s)) => {
      Ok(Spanned::new(Term::Word(s.clone()), span))
    }
    Token::Unknown(c) => Err(Diagnostic {
      full_source: cursor.source.to_string(),
      error_offset: span.start,
      error_message: format!("Unexpected character: {c}"),
    }),
    _ => Err(Diagnostic {
      full_source: cursor.source.to_string(),
      error_offset: span.start,
      error_message: "expected term".to_string(),
    }),
  }
}

#[cfg(test)]
#[path = "term_test.rs"]
mod term_test;
