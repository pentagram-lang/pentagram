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
#[command(name = "0")]
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
    let content = fs::read_to_string(path).await?;
    let path_str = path.to_string_lossy();
    return execute_tests(db, &[(&path_str, &content)], output)
      .map_err(anyhow::Error::new);
  }

  let mut paths = collect_penta_files(path).await?;
  if paths.is_empty() {
    return Ok(());
  }
  paths.sort();

  let mut loaded = Vec::with_capacity(paths.len());
  for entry_path in paths {
    let content = fs::read_to_string(&entry_path).await?;
    let path_str = entry_path.to_string_lossy().into_owned();
    loaded.push((path_str, content));
  }

  let files: Vec<(&str, &str)> = loaded
    .iter()
    .map(|(path_str, content)| (path_str.as_str(), content.as_str()))
    .collect();
  execute_tests(db, &files, output).map_err(anyhow::Error::new)
}

async fn collect_penta_files(dir: &Path) -> AnyhowResult<Vec<PathBuf>> {
  let mut entries = fs::read_dir(dir).await?;
  let mut paths = Vec::new();
  while let Some(entry) = entries.next_entry().await? {
    let entry_path = entry.path();
    if entry_path.is_file()
      && entry_path.extension().and_then(|s| s.to_str()) == Some("penta")
    {
      paths.push(entry_path);
    }
  }
  Ok(paths)
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
          if !files.is_empty() {
            for file in files {
              writeln!(output, "-- Change detected: {:?} --", file.name)?;
            }
            run_harness(db, path, output).await?;
          }
        }
      }
      _ => {}
    }
    output.flush()?;
  }
  Ok(())
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
