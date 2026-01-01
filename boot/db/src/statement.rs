use crate::file::FileId;
use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::term::SpannedTerm;
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct StatementId(pub String);

impl fmt::Display for StatementId {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    write!(f, "{}", self.0)
  }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StatementRecord {
  pub id: StatementId,
  pub file_id: FileId,
  pub body: Vec<SpannedTerm>,
  pub content_hash: ContentHash,
  pub generation: Generation,
  pub index: u32,
}
