use crate::token_cursor::TokenCursor;
use crate::token_cursor::advance_token_cursor;
use boot_db::Diagnostic;
use boot_db::DiagnosticResult;
use boot_db::IdentifierTokenKind;
use boot_db::LiteralTokenKind;
use boot_db::Span;
use boot_db::SpannedTerm;
use boot_db::Term;
use boot_db::Token;
use boot_db::Value;

pub(crate) fn parse_term(
  cursor: &mut TokenCursor<'_>,
) -> DiagnosticResult<SpannedTerm> {
  let Some(token) = cursor.head else {
    return Err(Diagnostic {
      file_id: cursor.file_id.clone(),
      span: Span {
        start: cursor.source_len,
        end: cursor.source_len,
      },
      error_message: "Unexpected end of input, expected term".to_string(),
    });
  };
  advance_token_cursor(cursor);

  let span = token.span;
  match &token.value {
    Token::Literal(LiteralTokenKind::Integer(i)) => {
      Ok(SpannedTerm::new(Term::Literal(Value::Integer(*i)), span))
    }
    Token::Literal(LiteralTokenKind::String(s)) => Ok(SpannedTerm::new(
      Term::Literal(Value::String(s.clone())),
      span,
    )),
    Token::Identifier(IdentifierTokenKind::Word(s)) => {
      Ok(SpannedTerm::new(Term::Word(s.clone()), span))
    }
    Token::Unknown(c) => Err(Diagnostic {
      file_id: cursor.file_id.clone(),
      span,
      error_message: format!("Unexpected character: {c}"),
    }),
    _ => Err(Diagnostic {
      file_id: cursor.file_id.clone(),
      span,
      error_message: "expected term".to_string(),
    }),
  }
}

#[cfg(test)]
#[path = "term_test.rs"]
mod term_test;
