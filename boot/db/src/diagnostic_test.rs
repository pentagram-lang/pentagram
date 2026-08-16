use super::*;
use crate::file::FileRecord;
use crate::generation::Generation;
use crate::hash::ContentHash;
use pretty_assertions::assert_eq;

#[test]
fn test_resolve_diagnostic() {
  let mut db = Database::default();
  let file_id = FileId("test.penta".to_string());
  db.files.push(FileRecord {
    id: file_id.clone(),
    path: "test.penta".to_string(),
    source: "1 2 +\nassert".to_string(),
    content_hash: ContentHash([0; 32]),
    generation: Generation::NewOnly,
  });

  let diagnostic = Diagnostic {
    file_id,
    span: Span { start: 6, end: 12 },
    error_message: "Assertion failed".to_string(),
  };

  let resolved = resolve_diagnostic(&diagnostic, &db);
  assert_eq!(
    resolved,
    ResolvedDiagnostic {
      path: "test.penta".to_string(),
      full_source: "1 2 +\nassert".to_string(),
      span: Span { start: 6, end: 12 },
      error_message: "Assertion failed".to_string(),
    }
  );
}

#[test]
fn test_diagnostic_display() {
  let diagnostic = Diagnostic {
    file_id: FileId("main.penta".to_string()),
    span: Span { start: 4, end: 10 },
    error_message: "Syntax error".to_string(),
  };
  assert_eq!(
    diagnostic.to_string(),
    "Error in main.penta at 4..10: Syntax error"
  );
}

#[test]
fn test_resolved_diagnostic_display() {
  let resolved = ResolvedDiagnostic {
    path: "main.penta".to_string(),
    full_source: "def foo".to_string(),
    span: Span { start: 0, end: 3 },
    error_message: "Syntax error".to_string(),
  };
  assert_eq!(resolved.to_string(), "Syntax error");
}

#[test]
fn test_get_diagnostic_line_info_multiline() {
  let resolved = ResolvedDiagnostic {
    path: "test.penta".to_string(),
    full_source: "line one\nline two\nline three".to_string(),
    span: Span { start: 14, end: 17 },
    error_message: "Error".to_string(),
  };

  let (line_num, col, line_str) = get_diagnostic_line_info(&resolved);
  assert_eq!(line_num, 2);
  assert_eq!(col, 5);
  assert_eq!(line_str, "line two");
}

#[test]
fn test_get_diagnostic_line_info_eof() {
  let resolved = ResolvedDiagnostic {
    path: "test.penta".to_string(),
    full_source: "abc\ndef".to_string(),
    span: Span { start: 7, end: 7 },
    error_message: "Unexpected EOF".to_string(),
  };

  let (line_num, col, line_str) = get_diagnostic_line_info(&resolved);
  assert_eq!(line_num, 2);
  assert_eq!(col, 3);
  assert_eq!(line_str, "def");
}

#[test]
fn test_get_diagnostic_line_info_empty() {
  let resolved = ResolvedDiagnostic {
    path: "test.penta".to_string(),
    full_source: String::new(),
    span: Span { start: 0, end: 0 },
    error_message: "Empty file error".to_string(),
  };

  let (line_num, col, line_str) = get_diagnostic_line_info(&resolved);
  assert_eq!(line_num, 1);
  assert_eq!(col, 0);
  assert_eq!(line_str, "");
}
