use crate::builtin::Builtin;
use crate::function::FunctionId;
use crate::hash::ContentHash;
use crate::value::Value;
use blake3::Hasher;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Term {
  Literal(Value),
  Word(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ResolvedWord {
  Builtin(Builtin),
  Function(FunctionId),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ResolvedTerm {
  Literal(Value),
  Word(ResolvedWord),
}

pub fn hash_terms(terms: &[Term]) -> ContentHash {
  let mut hasher = Hasher::new();
  for t in terms {
    update_term_hash(t, &mut hasher);
  }
  hasher.finalize().into()
}

pub fn update_term_hash(term: &Term, hasher: &mut Hasher) {
  match term {
    Term::Literal(v) => {
      hasher.update(b"lit");
      match v {
        Value::Integer(i) => hasher.update(&i.to_le_bytes()),
        Value::String(s) => hasher.update(s.as_bytes()),
        Value::Boolean(b) => hasher.update(&[u8::from(*b)]),
      };
    }
    Term::Word(w) => {
      hasher.update(b"word");
      hasher.update(w.as_bytes());
    }
  }
}

pub fn hash_resolved_terms(terms: &[ResolvedTerm]) -> ContentHash {
  let mut hasher = Hasher::new();
  for t in terms {
    update_resolved_term_hash(t, &mut hasher);
  }
  hasher.finalize().into()
}

pub fn update_resolved_term_hash(
  term: &ResolvedTerm,
  hasher: &mut Hasher,
) {
  match term {
    ResolvedTerm::Literal(v) => {
      hasher.update(b"lit");
      match v {
        Value::Integer(i) => hasher.update(&i.to_le_bytes()),
        Value::String(s) => hasher.update(s.as_bytes()),
        Value::Boolean(b) => hasher.update(&[u8::from(*b)]),
      };
    }
    ResolvedTerm::Word(w) => {
      hasher.update(b"word");
      match w {
        ResolvedWord::Builtin(b) => {
          hasher.update(b"builtin");
          let b_byte = match b {
            Builtin::Add => 1,
            Builtin::Eq => 2,
            Builtin::Say => 3,
            Builtin::Assert => 4,
          };
          hasher.update(&[b_byte]);
        }
        ResolvedWord::Function(id) => {
          hasher.update(b"func");
          hasher.update(id.0.as_bytes());
        }
      }
    }
  }
}
