mod shell;
mod step;

use crate::shell::execute_shell;
use anyhow::Result as AnyhowResult;

#[tokio::main]
async fn main() -> AnyhowResult<()> {
  execute_shell().await
}
