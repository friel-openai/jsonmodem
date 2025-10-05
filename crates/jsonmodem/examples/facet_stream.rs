#![cfg(feature = "facet")]
#![allow(missing_docs)]

use std::collections::BTreeMap;

use facet::Facet;
use jsonmodem::{JsonModemFacet, ParserOptions};

type Result<T> = core::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Facet, Debug, Default, PartialEq)]
struct Credentials {
    user: String,
    scopes: Vec<String>,
}

#[derive(Facet, Debug, Default, PartialEq)]
struct Service {
    name: String,
    endpoints: Vec<String>,
    metadata: BTreeMap<String, String>,
}

#[derive(Facet, Debug, Default, PartialEq)]
struct Config {
    environment: String,
    retries: u8,
    credentials: Credentials,
    feature_flags: BTreeMap<String, bool>,
    services: Vec<Service>,
}

fn main() -> Result<()> {
    let mut facet = JsonModemFacet::<Config>::new(ParserOptions::default())?;
    let chunks = [
        "{\"environment\":\"production\",",
        "\"retries\":2,\"credentials\":{\"user\":\"ops\",",
        "\"scopes\":[\"deploy\",\"metrics\"]},",
        "\"feature_flags\":{\"dark_launch\":true,",
        "\"audit\":false},",
        "\"services\":[{\"name\":\"auth\",",
        "\"endpoints\":[\"/login\",\"/logout\"],",
        "\"metadata\":{\"tier\":\"critical\",",
        "\"language\":\"rust\"}},{\"name\":\"metrics\",",
        "\"endpoints\":[\"/scrape\"],",
        "\"metadata\":{\"tier\":\"support\"}}]}",
    ];

    for chunk in &chunks {
        if let Some(snapshot) = facet.feed(chunk)? {
            println!(
                "bytes={} partial={:#?}",
                snapshot.bytes_consumed, snapshot.value
            );
        }
    }

    let config = facet.finish()?;
    println!("final config: {config:#?}");
    Ok(())
}
