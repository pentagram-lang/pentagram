use super::*;
use boot_db::ContentHash;
use boot_db::FileId;
use boot_db::FileRecord;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_parse::ParsedModule;
use pretty_assertions::assert_eq;

#[test]
fn test_shred_function_change() {
  let mut db = Database::default();
  let name_id = FunctionId("foo".to_string());
  let file_id = FileId("test.penta".to_string());

  let parsed = ParsedModule {
    functions: vec![FunctionRecord {
      id: name_id.clone(),
      name: "foo".to_string(),
      file_id: file_id.clone(),
      body: vec![],
      content_hash: ContentHash([1; 32]),
      generation: Generation::NewOnly,
      index: 0,
    }],
    ..Default::default()
  };

  shred_module(&mut db, parsed);
  let expected_1 = vec![FunctionRecord {
    id: name_id.clone(),
    name: "foo".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
    index: 0,
  }];
  assert_eq!(db.functions, expected_1);

  db.functions[0].generation = Generation::OldOnly;

  let parsed_same = ParsedModule {
    functions: vec![FunctionRecord {
      id: name_id.clone(),
      name: "foo".to_string(),
      file_id: file_id.clone(),
      body: vec![],
      content_hash: ContentHash([1; 32]),
      generation: Generation::NewOnly,
      index: 0,
    }],
    ..Default::default()
  };

  shred_module(&mut db, parsed_same);
  let expected_2 = vec![FunctionRecord {
    id: name_id.clone(),
    name: "foo".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewAndOld,
    index: 0,
  }];
  assert_eq!(db.functions, expected_2);

  db.functions[0].generation = Generation::OldOnly;

  let parsed_diff = ParsedModule {
    functions: vec![FunctionRecord {
      id: name_id.clone(),
      name: "foo".to_string(),
      file_id: file_id.clone(),
      body: vec![],
      content_hash: ContentHash([2; 32]),
      generation: Generation::NewOnly,
      index: 0,
    }],
    ..Default::default()
  };

  shred_module(&mut db, parsed_diff);
  let expected_3 = vec![
    FunctionRecord {
      id: name_id.clone(),
      name: "foo".to_string(),
      file_id: file_id.clone(),
      body: vec![],
      content_hash: ContentHash([1; 32]),
      generation: Generation::OldOnly,
      index: 0,
    },
    FunctionRecord {
      id: name_id.clone(),
      name: "foo".to_string(),
      file_id,
      body: vec![],
      content_hash: ContentHash([2; 32]),
      generation: Generation::NewOnly,
      index: 0,
    },
  ];
  assert_eq!(db.functions, expected_3);
}

#[test]
fn test_shred_file_caching() {
  let mut db = Database::default();
  let path = "test.penta";
  let content = "def foo fn 1 end-fn";

  shred_file(&mut db, path, content).expect("Shred failed");

  let first_hash = db.files[0].content_hash;
  assert_eq!(
    db.files,
    vec![FileRecord {
      id: FileId(path.to_string()),
      path: path.to_string(),
      source: content.to_string(),
      content_hash: first_hash,
      generation: Generation::NewOnly,
    }]
  );

  db.files[0].generation = Generation::OldOnly;

  let parsed_2 =
    shred_file(&mut db, path, content).expect("Second shred failed");
  assert_eq!(parsed_2, ParsedModule::default());
  assert_eq!(
    db.files,
    vec![FileRecord {
      id: FileId(path.to_string()),
      path: path.to_string(),
      source: content.to_string(),
      content_hash: first_hash,
      generation: Generation::NewAndOld,
    }]
  );

  let content_3 = "def foo fn 2 end-fn";
  shred_file(&mut db, path, content_3).expect("Third shred failed");

  let third_hash = db.files[0].content_hash;
  assert_eq!(
    db.files,
    vec![FileRecord {
      id: FileId(path.to_string()),
      path: path.to_string(),
      source: content_3.to_string(),
      content_hash: third_hash,
      generation: Generation::NewOnly,
    }]
  );
}
