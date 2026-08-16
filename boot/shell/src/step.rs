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
        writeln!(stdout, "  {source_line}")?;
        writeln!(stdout, "  {:padding$}^", "", padding = caret_char_pos)?;
      } else {
        writeln!(stdout, "  In {}:", resolved.path)?;
        writeln!(stdout, "  {source_line}")?;
        writeln!(stdout, "  {:padding$}^", "", padding = caret_char_pos)?;
      }
    }
  }
  Ok(())
}
