use anyhow::Result;
use boot_eval::VM;
use boot_parser::parse;
use std::path::Path;
use tokio::fs;
use watchman_client::CanonicalPath;
use watchman_client::Connector;
use watchman_client::SubscriptionData;
use watchman_client::expr::Expr;
use watchman_client::fields::NameOnly;
use watchman_client::pdu::SubscribeRequest;

pub async fn run_watch(path: &Path) -> Result<()> {
  let abs_path = CanonicalPath::canonicalize(path)?;
  println!("Watching: {:?}", abs_path);

  let client = Connector::new().connect().await?;
  let root = client.resolve_root(abs_path).await?;

  let (mut sub, _) = client
    .subscribe::<NameOnly>(
      &root,
      SubscribeRequest {
        expression: Some(Expr::Suffix(vec!["penta".into()])), // Watch .penta files
        fields: vec!["name"],
        ..Default::default()
      },
    )
    .await?;

  println!("Performing initial test run...");
  if let Err(e) = run_once(path).await {
    println!("Initial run error: {}", e);
  }

  loop {
    match sub.next().await? {
      SubscriptionData::Canceled => break,
      SubscriptionData::FilesChanged(result) => {
        if let Some(files) = result.files {
          for file in files {
            println!("-- Change detected: {:?} --", file.name);
            // We need to reconstruct the full path or just read relative to root.
            // Ideally we read the file content.
            let full_path = path.join(&*file.name); // 'path' is roughly the root here
            if let Err(e) = run_test_file(&full_path).await {
              println!("Error: {}", e);
            }
          }
        }
      }
      _ => {}
    }
  }

  Ok(())
}

pub async fn run_once(path: &Path) -> Result<()> {
  if path.is_file() {
    run_test_file(path).await
  } else {
    // Simple directory traversal for now
    let mut entries = fs::read_dir(path).await?;
    while let Some(entry) = entries.next_entry().await? {
      let path = entry.path();
      if path.extension().and_then(|s| s.to_str()) == Some("penta") {
        run_test_file(&path).await?;
      }
    }
    Ok(())
  }
}

async fn run_test_file(path: &Path) -> Result<()> {
  let content = fs::read_to_string(path).await?;
  let terms =
    parse(&content).map_err(|e| anyhow::anyhow!("Parse error: {}", e))?;

  println!("Running tests in {:?}", path);
  let mut vm = VM::default(); // This runs all top-level terms, including 'test' blocks (which eval their body immediately)
  if let Err(e) = vm.eval(terms) {
    println!("FAIL: {}", e);
  } else {
    println!("PASS");
  }
  Ok(())
}
