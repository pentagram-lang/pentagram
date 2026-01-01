use crate::db::Database;
use crate::file::FileId;
use crate::span::Span;
use std::error::Error;
use std::fmt::Display;
use std::fmt::Formatter;
use std::fmt::Result as FormatResult;

#[derive(PartialEq, Eq, Debug)]
pub struct Diagnostic {
  pub file_id: FileId,
  pub span: Span,
  pub error_message: String,
}

pub fn resolve_diagnostic(
  diagnostic: &Diagnostic,
  db: &Database,
) -> ResolvedDiagnostic {
  let file = db
    .files
    .iter()
    .find(|f| f.id == diagnostic.file_id)
    .expect("File not found in database for diagnostic resolution");

  ResolvedDiagnostic {
    path: file.path.clone(),
    full_source: file.source.clone(),
    span: diagnostic.span,
    error_message: diagnostic.error_message.clone(),
  }
}

impl Display for Diagnostic {
  fn fmt(&self, f: &mut Formatter<'_>) -> FormatResult {
    write!(
      f,
      "Error in {} at {}: {}",
      self.file_id, self.span, self.error_message
    )
  }
}

impl Error for Diagnostic {}

pub type DiagnosticResult<T> = Result<T, Diagnostic>;

#[derive(PartialEq, Eq, Debug, Clone)]
pub struct ResolvedDiagnostic {
  pub path: String,
  pub full_source: String,
  pub span: Span,
  pub error_message: String,
}

impl Display for ResolvedDiagnostic {
  fn fmt(&self, f: &mut Formatter<'_>) -> FormatResult {
    write!(f, "{}", self.error_message)
  }
}

impl Error for ResolvedDiagnostic {}

pub type ResolvedDiagnosticResult<T> = Result<T, ResolvedDiagnostic>;

pub fn get_diagnostic_line_info(
  diagnostic: &ResolvedDiagnostic,
) -> (usize, usize, String) {
  let mut line_num = 0;
  let mut line_start_offset = 0;
  let mut column_char_offset = 0;
  let mut current_char_idx = 0;

  for (byte_idx, char_val) in diagnostic.full_source.char_indices() {
    if byte_idx == diagnostic.span.start {
      column_char_offset = current_char_idx;
      break;
    }
    if char_val == '\n' {
      line_num += 1;
      line_start_offset = byte_idx + char_val.len_utf8();
      current_char_idx = 0;
    } else {
      current_char_idx += 1;
    }
  }

  let line_end_offset = diagnostic.full_source[line_start_offset ..]
    .find('\n')
    .map_or(diagnostic.full_source.len(), |idx| line_start_offset + idx);

  let source_line = diagnostic.full_source
    [line_start_offset .. line_end_offset]
    .to_string();

  (line_num + 1, column_char_offset, source_line)
}
