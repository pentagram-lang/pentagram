use crate::generation::Generation;
use crate::hash::ContentHash;
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct FileId(pub String);

impl fmt::Display for FileId {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    write!(f, "{}", self.0)
  }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileRecord {
  pub id: FileId,
  pub path: String,
  pub source: String,
  pub content_hash: ContentHash,
  pub generation: Generation,
}
