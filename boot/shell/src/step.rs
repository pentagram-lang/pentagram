use anyhow::Result as AnyhowResult;
use boot_db::get_diagnostic_line_info;
use boot_engine::Database;
use boot_engine::execute_repl;
use std::io::Write;

pub(crate) fn step_repl(
  db: &mut Database,
  line: &str,
  stdout: &mut (dyn Write + Send),
) -> AnyhowResult<()> {
  if let Err(resolved) = execute_repl(db, line, stdout) {
    let (_line_num, caret_char_pos, source_line): (usize, usize, String) =
      get_diagnostic_line_info(&resolved);

    writeln!(stdout, "Error: {}", resolved.error_message)?;

    if !source_line.is_empty() {
      if resolved.full_source == line {
        // Special case: diagnostic matches current input, only print marker --
        // Wait, lining up with prompt means we need prompt length.
        // For now, let's just print the context normally but we can refine.
        writeln!(stdout, "  {source_line}")?;
        writeln!(stdout, "  {:padding$}^", "", padding = caret_char_pos)?;
      } else {
        writeln!(stdout, "  In {}:", resolved.file_id)?;
        writeln!(stdout, "  {source_line}")?;
        writeln!(stdout, "  {:padding$}^", "", padding = caret_char_pos)?;
      }
    }
  }
  Ok(())
}
