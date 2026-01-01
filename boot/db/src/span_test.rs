use super::*;
use blake3::Hasher;
use pretty_assertions::assert_eq;

#[test]
fn test_span_len_and_is_empty() {
  let span = Span { start: 5, end: 12 };
  assert_eq!(span.len(), 7);
  assert_eq!(span.is_empty(), false);

  let empty_span = Span { start: 5, end: 5 };
  assert_eq!(empty_span.len(), 0);
  assert_eq!(empty_span.is_empty(), true);
}

#[test]
fn test_span_merge() {
  let left = Span { start: 3, end: 8 };
  let right = Span { start: 6, end: 14 };
  assert_eq!(left.merge(right), Span { start: 3, end: 14 });

  let disjoint_left = Span { start: 2, end: 4 };
  let disjoint_right = Span { start: 10, end: 15 };
  assert_eq!(
    disjoint_left.merge(disjoint_right),
    Span { start: 2, end: 15 }
  );
}

#[test]
fn test_span_display() {
  let span = Span { start: 10, end: 25 };
  assert_eq!(span.to_string(), "10..25");
}

#[test]
fn test_span_hash_update() {
  let span = Span { start: 10, end: 20 };
  let mut hasher = Hasher::new();
  update_span_hash(&span, &mut hasher);
  let hash1 = hasher.finalize();

  let mut hasher_expected = Hasher::new();
  hasher_expected.update(&10usize.to_le_bytes());
  hasher_expected.update(&20usize.to_le_bytes());
  let hash2 = hasher_expected.finalize();

  assert_eq!(hash1, hash2);
}

#[test]
fn test_spanned_new_and_map() {
  let span = Span { start: 1, end: 5 };
  let spanned = Spanned::new("hello", span);
  assert_eq!(
    spanned,
    Spanned {
      value: "hello",
      span: Span { start: 1, end: 5 }
    }
  );

  let mapped = spanned.map(str::len);
  assert_eq!(
    mapped,
    Spanned {
      value: 5,
      span: Span { start: 1, end: 5 }
    }
  );
}
