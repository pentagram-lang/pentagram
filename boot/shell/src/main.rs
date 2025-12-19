use anyhow::Result;
use anyhow::anyhow;
use clap::Parser;
use clap::Subcommand;
use rustyline_async::Readline;
use rustyline_async::ReadlineEvent;
use std::io::Write;
use std::path::PathBuf;

#[derive(Parser)]
#[command(version, about, long_about = None)]
struct Cli {
  #[command(subcommand)]
  command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
  /// Run a script
  Run { file: PathBuf },
  /// Run tests
  Test {
    /// Directory or file to watch (default: current dir)
    #[arg(default_value = ".")]
    path: PathBuf,
    /// Watch for changes
    #[arg(short, long)]
    watch: bool,
  },
}

#[tokio::main]
async fn main() -> Result<()> {
  let cli = Cli::parse();

  match cli.command {
    Some(Commands::Run { file }) => run_file(file).await,
    Some(Commands::Test { path, watch }) => {
      if watch {
        boot_test::run_watch(&path).await
      } else {
        boot_test::run_once(&path).await
      }
    }
    None => run_repl().await,
  }
}

async fn run_file(path: PathBuf) -> Result<()> {
  let content = tokio::fs::read_to_string(&path).await?;
  let terms = boot_parser::parse(&content)
    .map_err(|e| anyhow!("Parse error: {}", e))?;
  let mut vm = boot_eval::VM::default();
  vm.eval(terms)?;

  // If the file defines 'main', call it
  // Check if 'main' is in the dictionary (internal API access might be needed, or just try running 'main' term)
  // For now, let's just assume the file does work at the top level or defines main.
  // The prompt example: "def main fn 'Hello world!' say end-fn,"
  // This just defines it. We need to call it if it exists.
  // Let's manually trigger 'main' call.
  match vm.eval(vec![boot_types::Term::Word("main".to_string())]) {
    Ok(_) => {}
    Err(e) => {
      // If main doesn't exist or fails, that's fine/expected if script was just top-level code.
      // But prompt implies 'run' command calls main.
      // If the error is "Unknown word: main", we can ignore it maybe?
      // Or explicitly check dictionary? VM doesn't expose dictionary publicly yet.
      // Let's just print error if it's not "Unknown word: main".
      if !e.to_string().contains("Unknown word: main") {
        return Err(e);
      }
    }
  }

  Ok(())
}

async fn run_repl() -> Result<()> {
  let (mut readline, mut stdout) = Readline::new("boot> ".to_owned())?;
  let mut vm = boot_eval::VM::new(Box::new(stdout.clone()));

  loop {
    match readline.readline().await {
      Ok(ReadlineEvent::Line(line)) => {
        let line = line.trim();
        if line.is_empty() {
          continue;
        }
        readline.add_history_entry(line.to_owned());

        match boot_parser::parse(line) {
          Ok(terms) => {
            if let Err(e) = vm.eval(terms) {
              writeln!(stdout, "Error: {}", e)?;
            } else {
              let stack = vm.take_stack();
              if !stack.is_empty() {
                write!(stdout, "[")?;
                for v in stack {
                  write!(stdout, " {}", v)?;
                }
                writeln!(stdout, " ]")?;
              }
            }
          }
          Err(e) => {
            writeln!(stdout, "Parse Error: {}", e)?;
          }
        }
      }
      Ok(ReadlineEvent::Eof) => break,
      Ok(ReadlineEvent::Interrupted) => {
        writeln!(stdout, "^C")?;
        // Maybe clear stack?
      }
      Err(e) => {
        writeln!(stdout, "Error: {}", e)?;
        break;
      }
    }
  }
  Ok(())
}
