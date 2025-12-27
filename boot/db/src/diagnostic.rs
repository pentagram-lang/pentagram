use std::error::Error;
use std::fmt::Display;
use std::fmt::Formatter;
use std::fmt::Result as FormatResult;

#[derive(PartialEq, Eq, Debug)]
pub struct Diagnostic {
  pub full_source: String,
  pub error_offset: usize,
  pub error_message: String,
}

impl Display for Diagnostic {
  fn fmt(&self, f: &mut Formatter<'_>) -> FormatResult {
    let (_, caret_char_pos, source_line) = get_diagnostic_line_info(self);

    write!(f, "Error: {}", self.error_message)?;
    if !source_line.is_empty() {
      writeln!(f)?;
      writeln!(f, "  {source_line}")?;
      write!(f, "  {:padding$}^", "", padding = caret_char_pos)?;
    }
    Ok(())
  }
}

impl Error for Diagnostic {}

pub fn get_diagnostic_line_info(
  diagnostic: &Diagnostic,
) -> (usize, usize, String) {
  let mut line_num = 0;
  let mut line_start_offset = 0;
  let mut column_char_offset = 0;
  let mut current_char_idx = 0;

  for (byte_idx, char_val) in diagnostic.full_source.char_indices() {
    if byte_idx == diagnostic.error_offset {
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
