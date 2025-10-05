#![cfg(feature = "facet")]
#![allow(missing_docs)]

use facet::Facet;
use jsonmodem::{JsonModemFacet, JsonModemFacetError, JsonModemFacetOptions, ParserOptions};

#[derive(Facet, Debug, Default, PartialEq, Clone)]
struct TestStruct {
    count: u32,
    active: bool,
    name: String,
}

#[test]
fn streams_struct_snapshots() {
    let mut facet = JsonModemFacet::<TestStruct>::new(ParserOptions::default()).unwrap();
    let chunks = [
        "{\"count\":",
        "7,\"active\":",
        "true,\"name\":",
        "\"alpha\"}",
    ];

    let mut observed = Vec::new();
    let mut consumed = 0usize;
    for chunk in chunks {
        if let Some(snapshot) = facet.feed(chunk).unwrap() {
            consumed = snapshot.bytes_consumed;
            observed.push((snapshot.value.clone(), snapshot.is_final));
        }
    }

    let final_value = facet.finish().unwrap();
    assert_eq!(final_value.count, 7);
    assert!(final_value.active);
    assert_eq!(final_value.name, "alpha");

    assert_eq!(consumed, chunks.iter().map(|c| c.len()).sum());
    assert!(!observed.is_empty());
    assert!(observed.last().unwrap().1);
}

#[repr(C)]
#[derive(Facet, Debug, Default, PartialEq, Clone)]
enum Event {
    #[default]
    Idle,
    Tick {
        id: u64,
        enabled: bool,
    },
}

#[test]
fn handles_enums_and_arrays() {
    #[derive(Facet, Debug, Default, PartialEq)]
    struct Wrapper {
        events: Vec<Event>,
    }

    let mut facet = JsonModemFacet::<Wrapper>::new(ParserOptions::default()).unwrap();
    let chunks = [
        "{\"events\":[",
        "{\"Tick\":{\"id\":1,",
        "\"enabled\":false}},",
        "{\"Tick\":{\"id\":2,\"enabled\":true}}]}",
    ];

    for chunk in &chunks {
        // Partial snapshots are optional but should not error.
        let _ = facet.feed(chunk).unwrap();
    }

    let wrapper = facet.finish().unwrap();
    assert_eq!(wrapper.events.len(), 2);
    assert_eq!(
        wrapper.events[0],
        Event::Tick {
            id: 1,
            enabled: false
        }
    );
    assert_eq!(
        wrapper.events[1],
        Event::Tick {
            id: 2,
            enabled: true
        }
    );
}

#[test]
fn can_disable_partial_snapshots() {
    let options = JsonModemFacetOptions::new().with_partial_snapshots(false);
    let mut facet =
        JsonModemFacet::<TestStruct>::with_options(ParserOptions::default(), options).unwrap();

    assert!(
        facet
            .feed("{\"count\":1,\"active\":false,\"name\":\"n\"}")
            .unwrap()
            .is_none()
    );

    let value = facet.finish().unwrap();
    assert_eq!(value.count, 1);
    assert!(!value.active);
    assert_eq!(value.name, "n");
}

#[test]
fn rejects_malformed_json() {
    let mut facet = JsonModemFacet::<TestStruct>::new(ParserOptions::default()).unwrap();
    match facet.feed("{\"count\":}") {
        Err(JsonModemFacetError::Parser(_)) => {}
        Err(other) => panic!("unexpected error: {other:?}"),
        Ok(_) => panic!("expected parser error"),
    }
}
