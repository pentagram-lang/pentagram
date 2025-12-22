use anyhow::Result as AnyhowResult;
use boot_db::Diagnostic;
use boot_db::get_diagnostic_line_info;
use boot_engine::Database;
use boot_engine::execute_repl;
use std::io::Write;

pub(crate) fn step_repl(
  db: &mut Database,
  line: &str,
  stdout: &mut (dyn Write + Send),
) -> AnyhowResult<()> {
  if let Err(e) = execute_repl(db, line, stdout) {
    if let Some(diagnostic) = e.downcast_ref::<Diagnostic>() {
      let (_line_num, caret_char_pos, _source_line) =
        get_diagnostic_line_info(diagnostic);

      writeln!(
        stdout,
        "      {:padding$}^",
        "",
        padding = caret_char_pos
      )?;
      writeln!(stdout, "      {}", diagnostic.error_message)?;
    } else {
      writeln!(stdout, "Error: {e}")?;
    }
  }
  Ok(())
}
