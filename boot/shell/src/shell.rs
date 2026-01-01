use crate::step::step_repl;
use anyhow::Result as AnyhowResult;
use boot_engine::Database;
use boot_engine::execute_file;
use boot_engine::execute_tests;
use clap::Parser;
use clap::Subcommand;
use rustyline_async::Readline;
use rustyline_async::ReadlineEvent;
use std::io::Write;
use std::io::stdout;
use std::path::Path;
use std::path::PathBuf;
use tokio::fs;
use watchman_client::CanonicalPath;
use watchman_client::Connector;
use watchman_client::SubscriptionData;
use watchman_client::expr::Expr;
use watchman_client::fields::NameOnly;
use watchman_client::pdu::SubscribeRequest;

#[derive(Parser)]
#[command(name = "pt")]
#[command(about = "Pentagram boot shell", long_about = None)]
struct Cli {
  #[command(subcommand)]
  command: Option<Commands>,
  /// Optional file or directory to run (legacy mode)
  path: Option<PathBuf>,
}

#[derive(Subcommand)]
enum Commands {
  /// Run tests incrementally
  Test {
    path: PathBuf,
    /// Watch for changes
    #[arg(short, long)]
    watch: bool,
  },
  /// Start the REPL
  Repl,
  /// Run a file's 'main' function
  Run { path: PathBuf },
}

pub(crate) async fn execute_shell() -> AnyhowResult<()> {
  let cli = Cli::parse();
  let mut db = Database::default();
  match cli.command {
    Some(Commands::Test { path, watch }) => {
      if watch {
        run_watch(&mut db, &path, &mut stdout()).await?;
      } else {
        run_harness(&mut db, &path, &mut stdout()).await?;
      }
    }
    Some(Commands::Repl) => {
      run_repl(&mut db).await?;
    }
    Some(Commands::Run { path }) => {
      let content = fs::read_to_string(&path).await?;
      let path_str = path.to_string_lossy();
      execute_file(&mut db, &path_str, &content, &mut stdout())?;
    }
    None => {
      if let Some(path) = cli.path {
        if path.is_dir() {
          run_harness(&mut db, &path, &mut stdout()).await?;
        } else {
          let content = fs::read_to_string(&path).await?;
          let path_str = path.to_string_lossy();
          execute_file(&mut db, &path_str, &content, &mut stdout())?;
        }
      } else {
        run_repl(&mut db).await?;
      }
    }
  }
  Ok(())
}

async fn run_harness(
  db: &mut Database,
  path: &Path,
  output: &mut (dyn Write + Send),
) -> AnyhowResult<()> {
  if path.is_file() {
    run_file(db, path, output).await?;
  } else {
    let mut entries = fs::read_dir(path).await?;
    while let Some(entry) = entries.next_entry().await? {
      let path = entry.path();
      if path.extension().and_then(|s| s.to_str()) == Some("penta") {
        run_file(db, &path, output).await?;
      }
    }
  }
  Ok(())
}

async fn run_watch(
  db: &mut Database,
  path: &Path,
  output: &mut (dyn Write + Send),
) -> AnyhowResult<()> {
  let abs_path = CanonicalPath::canonicalize(path)?;
  writeln!(output, "Watching: {abs_path:?}")?;
  let client = Connector::new().connect().await?;
  let root = client.resolve_root(abs_path).await?;
  let root_path = root.path().clone();
  let (mut sub, _) = client
    .subscribe::<NameOnly>(
      &root,
      SubscribeRequest {
        expression: Some(Expr::Suffix(vec!["penta".into()])),
        fields: vec!["name"],
        ..Default::default()
      },
    )
    .await?;
  writeln!(output, "Performing initial test run...")?;
  run_harness(db, path, output).await?;
  loop {
    match sub.next().await? {
      SubscriptionData::Canceled => break,
      SubscriptionData::FilesChanged(result) => {
        if let Some(files) = result.files {
          for file in files {
            writeln!(output, "-- Change detected: {:?} --", file.name)?;
            let full_path = root_path.join(&*file.name);
            if full_path.exists() {
              run_file(db, &full_path, output).await?;
            }
          }
        }
      }
      _ => {}
    }
    output.flush()?;
  }
  Ok(())
}

async fn run_file(
  db: &mut Database,
  path: &Path,
  output: &mut (dyn Write + Send),
) -> AnyhowResult<()> {
  let content = fs::read_to_string(path).await?;
  let path_str = path.to_string_lossy();
  execute_tests(db, &[(&path_str, &content)], output)
    .map_err(anyhow::Error::new)
}

async fn run_repl(db: &mut Database) -> AnyhowResult<()> {
  let (mut rl, mut stdout_handle) = Readline::new("boot> ".to_string())?;
  loop {
    match rl.readline().await {
      Ok(ReadlineEvent::Line(line)) => {
        let line = line.trim();
        if line.is_empty() {
          continue;
        }
        rl.add_history_entry(line.to_string());
        if let Err(e) = step_repl(db, line, &mut stdout_handle) {
          writeln!(stdout_handle, "Error: {e}")?;
        }
        stdout_handle.flush()?;
      }
      Ok(ReadlineEvent::Eof | ReadlineEvent::Interrupted) => break,
      Err(e) => {
        writeln!(stdout_handle, "Readline error: {e}")?;
        break;
      }
    }
  }
  Ok(())
}

#[cfg(test)]
#[path = "shell_test.rs"]
mod shell_test;
