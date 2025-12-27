use crate::file::FileId;
use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::term::Term;
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct TestId(pub String);

impl fmt::Display for TestId {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    write!(f, "{}", self.0)
  }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TestRecord {
  pub id: TestId,
  pub file_id: FileId,
  pub body: Vec<Term>,
  pub content_hash: ContentHash,
  pub generation: Generation,
  pub index: u32,
}
