use super::*;
use boot_db::ContentHash;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::hash_terms;
use boot_lex::lex_source;

#[test]
fn test_parse_repl_merge() {
  let source = "def new_fn fn end-fn";
  let ts = lex_source("repl", source, ContentHash([0; 32])).unwrap();

  let old_funcs = vec![];
  let old_tests = vec![];

  let module =
    parse_repl_module("repl", source, &ts, old_funcs, old_tests).unwrap();

  let expected = ParsedModule {
    functions: vec![FunctionRecord {
      id: FunctionId("new_fn".to_string()),
      name: "new_fn".to_string(),
      file_id: FileId("repl".to_string()),
      body: vec![],
      content_hash: hash_terms(&[]),
      generation: Generation::NewOnly,
      index: 0,
    }],
    tests: vec![],
    statements: vec![],
  };
  assert_eq!(module, expected);
}
