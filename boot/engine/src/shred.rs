use anyhow::Result as AnyhowResult;
use blake3::Hasher;
use boot_db::ContentHash;
use boot_db::Database;
use boot_db::FileId;
use boot_db::FileRecord;
use boot_db::Generation;
use boot_parse::ParsedModule;
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

      for f in &mut db.functions {
        if f.file_id == file_id {
          f.generation = Generation::NewAndOld;
        }
      }
      for t in &mut db.tests {
        if t.file_id == file_id {
          t.generation = Generation::NewAndOld;
        }
      }
      for s in &mut db.statements {
        if s.file_id == file_id {
          s.generation = Generation::NewAndOld;
        }
      }

      let statements = db
        .statements
        .iter()
        .filter(|s| s.file_id == file_id)
        .cloned()
        .collect();

      return Ok(ParsedModule {
        functions: vec![],
        tests: vec![],
        statements,
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

  let parsed_module =
    parse_source(path, content).map_err(|e| anyhow::anyhow!(e))?;

  shred_module(db, parsed_module.clone());

  Ok(parsed_module)
}

pub(crate) fn shred_module(
  db: &mut Database,
  parsed_module: ParsedModule,
) {
  let mut new_functions = parsed_module.functions;
  for existing in &mut db.functions {
    if existing.generation == Generation::OldOnly {
      if let Some(pos) = new_functions.iter().position(|nf| {
        nf.id == existing.id
          && nf.file_id == existing.file_id
          && nf.index == existing.index
          && nf.content_hash == existing.content_hash
      }) {
        existing.generation = Generation::NewAndOld;
        new_functions.swap_remove(pos);
      }
    }
  }
  db.functions.extend(new_functions);

  let mut new_tests = parsed_module.tests;
  for existing in &mut db.tests {
    if existing.generation == Generation::OldOnly {
      if let Some(pos) = new_tests.iter().position(|pt| {
        pt.id == existing.id
          && pt.file_id == existing.file_id
          && pt.index == existing.index
          && pt.content_hash == existing.content_hash
      }) {
        existing.generation = Generation::NewAndOld;
        new_tests.swap_remove(pos);
      }
    }
  }
  db.tests.extend(new_tests);

  let mut new_statements = parsed_module.statements;
  for existing in &mut db.statements {
    if existing.generation == Generation::OldOnly {
      if let Some(pos) = new_statements.iter().position(|ps| {
        ps.id == existing.id
          && ps.file_id == existing.file_id
          && ps.index == existing.index
          && ps.content_hash == existing.content_hash
      }) {
        existing.generation = Generation::NewAndOld;
        new_statements.swap_remove(pos);
      }
    }
  }
  db.statements.extend(new_statements);
}

pub(crate) fn shred_repl(db: &mut Database, parsed_module: ParsedModule) {
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

  shred_module(db, parsed_module);
}

#[cfg(test)]
#[path = "shred_test.rs"]
mod shred_test;
