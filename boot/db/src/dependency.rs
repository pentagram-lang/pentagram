use crate::function::FunctionId;
use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::tst::TestId;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DependencyFunctionRecord {
  pub id: FunctionId,
  pub content_hash: ContentHash,
  pub generation: Generation,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DependencyTestRecord {
  pub id: TestId,
  pub content_hash: ContentHash,
  pub generation: Generation,
}
