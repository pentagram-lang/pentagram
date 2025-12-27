use crate::file::FileId;
use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::term::ResolvedTerm;
use crate::tst::TestId;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedTestRecord {
  pub id: TestId,
  pub file_id: FileId,
  pub body: Vec<ResolvedTerm>,
  pub content_hash: ContentHash,
  pub generation: Generation,
}
