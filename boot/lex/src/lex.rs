use crate::char_cursor::CharCursor;
use crate::char_cursor::advance_char_cursor;
use crate::comment::lex_comment;
use crate::integer::lex_integer;
use crate::integer::lex_integer_negative;
use crate::punctuation::lex_punctuation;
use crate::string::lex_string;
use crate::whitespace::lex_whitespace;
use crate::word::lex_word;
use crate::word::lex_word_hyphen_prefix;
use crate::word::lex_word_plus_prefix;
use boot_db::ContentHash;
use boot_db::DiagnosticResult;
use boot_db::FileId;
use boot_db::Generation;
use boot_db::Span;
use boot_db::SpannedToken;
use boot_db::Token;
use boot_db::TokenStreamId;
use boot_db::TokenStreamRecord;
use boot_db::TriviaToken;

enum Termination {
  Check,
  None,
}

pub fn lex_source(
  path: &str,
  source: &str,
  content_hash: ContentHash,
) -> DiagnosticResult<TokenStreamRecord> {
  let mut cursor = CharCursor::new(source);
  let mut tokens = Vec::new();

  loop {
    let start = cursor.offset;

    let (kind, termination) = match cursor.head {
      Some(c) if c.is_whitespace() => {
        (lex_whitespace(&mut cursor), Termination::None)
      }
      Some('-') => (lex_hyphen(&mut cursor, start), Termination::Check),
      Some('+') => (lex_plus(&mut cursor, start), Termination::Check),
      Some(',') => (lex_punctuation(&mut cursor), Termination::None),
      Some('\'') => (lex_string(&mut cursor, start), Termination::Check),
      Some(c) if c.is_ascii_digit() => {
        (lex_integer(&mut cursor, start), Termination::Check)
      }
      Some(c) => (lex_word(&mut cursor, start, c), Termination::Check),
      None => break,
    };

    let end = cursor.offset;
    tokens.push(SpannedToken::new(kind, Span { start, end }));

    if let Termination::Check = termination {
      match cursor.head {
        Some(',') | None => {}
        Some(c) if c.is_whitespace() => {}
        _ => {
          tokens.push(SpannedToken::new(
            Token::Trivia(TriviaToken::InvalidTermination),
            Span { start, end },
          ));
        }
      }
    }
  }

  Ok(TokenStreamRecord {
    id: TokenStreamId(path.to_string()),
    file_id: FileId(path.to_string()),
    tokens,
    content_hash,
    generation: Generation::NewOnly,
  })
}

fn lex_hyphen(cursor: &mut CharCursor<'_>, start: usize) -> Token {
  advance_char_cursor(cursor);
  match cursor.head {
    Some('-') => {
      advance_char_cursor(cursor);
      lex_comment(cursor, start)
    }
    Some(c) if c.is_ascii_digit() => lex_integer_negative(cursor, start),
    _ => lex_word_hyphen_prefix(cursor, start),
  }
}

fn lex_plus(cursor: &mut CharCursor<'_>, start: usize) -> Token {
  advance_char_cursor(cursor);
  match cursor.head {
    Some(c) if c.is_ascii_digit() => lex_integer(cursor, start),
    _ => lex_word_plus_prefix(cursor, start),
  }
}

#[cfg(test)]
#[path = "lex_test.rs"]
mod lex_test;
