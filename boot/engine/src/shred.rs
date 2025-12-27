use anyhow::Result as AnyhowResult;
use blake3::Hasher;
use boot_db::ContentHash;
use boot_db::Database;
use boot_db::FileId;
use boot_db::FileRecord;
use boot_db::Generation;
use boot_db::TokenStreamRecord;
use boot_parse::ParsedModule;
use boot_parse::parse_repl_module;
use boot_parse::parse_source;

pub(crate) fn shred_file(
  db: &mut Database,
  path: &str,
  content: &str,
) -> AnyhowResult<ParsedModule> {
  let mut hasher = Hasher::new();
  hasher.update(content.as_bytes());

  let hash: ContentHash = hasher.finalize().into();
  let file_id = FileId(path.to_string());

  if let Some(existing) = db.files.iter_mut().find(|f| f.id == file_id) {
    if existing.content_hash == hash {
      existing.generation = Generation::NewAndOld;

      if let Some(ts) =
        db.token_streams.iter_mut().find(|ts| ts.file_id == file_id)
      {
        ts.generation = Generation::NewAndOld;
      }

      promote_items(db, &file_id);

      return Ok(ParsedModule {
        functions: vec![],
        tests: vec![],
        statements: db
          .statements
          .iter()
          .filter(|s| s.file_id == file_id)
          .cloned()
          .collect(),
      });
    }

    existing.content_hash = hash;
    existing.source = content.to_string();
    existing.generation = Generation::NewOnly;
  } else {
    db.files.push(FileRecord {
      id: file_id.clone(),
      path: path.to_string(),
      source: content.to_string(),
      content_hash: hash,
      generation: Generation::NewOnly,
    });
  }

  let token_stream = boot_lex::lex_source(path, content, hash)?;
  upsert_token_stream(db, &file_id, &token_stream);

  let parsed_module = parse_source(path, content, &token_stream)?;

  shred_module(db, parsed_module.clone());

  Ok(parsed_module)
}

pub(crate) fn shred_repl(
  db: &mut Database,
  line: &str,
) -> AnyhowResult<ParsedModule> {
  let file_id = FileId("repl".to_string());
  let dummy_hash = ContentHash([0; 32]);

  if let Some(existing) = db.files.iter_mut().find(|f| f.id == file_id) {
    existing.content_hash = dummy_hash;
    existing.generation = Generation::NewOnly;
  } else {
    db.files.push(FileRecord {
      id: file_id.clone(),
      path: "repl".to_string(),
      source: String::new(),
      content_hash: dummy_hash,
      generation: Generation::NewOnly,
    });
  }

  let token_stream = boot_lex::lex_source("repl", line, dummy_hash)?;
  upsert_token_stream(db, &file_id, &token_stream);

  let old_functions: Vec<_> = db
    .functions
    .iter()
    .filter(|f| f.file_id == file_id)
    .cloned()
    .collect();
  let old_tests: Vec<_> = db
    .tests
    .iter()
    .filter(|t| t.file_id == file_id)
    .cloned()
    .collect();

  let module = parse_repl_module(
    "repl",
    line,
    &token_stream,
    old_functions,
    old_tests,
  )?;

  shred_module(db, module.clone());

  Ok(module)
}

fn promote_items(db: &mut Database, file_id: &FileId) {
  for f in &mut db.functions {
    if f.file_id == *file_id {
      f.generation = Generation::NewAndOld;
    }
  }
  for t in &mut db.tests {
    if t.file_id == *file_id {
      t.generation = Generation::NewAndOld;
    }
  }
  for s in &mut db.statements {
    if s.file_id == *file_id {
      s.generation = Generation::NewAndOld;
    }
  }
}

fn upsert_token_stream(
  db: &mut Database,
  file_id: &FileId,
  token_stream: &TokenStreamRecord,
) {
  if let Some(ts) = db
    .token_streams
    .iter_mut()
    .find(|ts| ts.file_id == *file_id)
  {
    ts.tokens.clone_from(&token_stream.tokens);
    ts.content_hash = token_stream.content_hash;
    ts.generation = Generation::NewOnly;
  } else {
    db.token_streams.push(token_stream.clone());
  }
}

fn shred_module(db: &mut Database, parsed_module: ParsedModule) {
  macro_rules! reconcile_records {
    ($db_records:expr, $new_records:expr) => {
      for existing in $db_records.iter_mut() {
        if existing.generation == Generation::OldOnly {
          if let Some(pos) = $new_records.iter().position(|new_item| {
            new_item.id == existing.id
              && new_item.file_id == existing.file_id
              && new_item.index == existing.index
              && new_item.content_hash == existing.content_hash
          }) {
            existing.generation = Generation::NewAndOld;
            $new_records.swap_remove(pos);
          }
        }
      }
      $db_records.extend($new_records);
    };
  }

  let mut new_functions = parsed_module.functions;
  reconcile_records!(db.functions, new_functions);

  let mut new_tests = parsed_module.tests;
  reconcile_records!(db.tests, new_tests);

  let mut new_statements = parsed_module.statements;
  reconcile_records!(db.statements, new_statements);
}

#[cfg(test)]
#[path = "shred_test.rs"]
mod shred_test;
