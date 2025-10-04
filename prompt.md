create an execspec for a JsonModemFacet implementation in the jsonmodem crate. JsonModemFacet enables us the following:

```rs
    #[derive(facet::Facet)]
    struct TestStruct {
        name: String,
        age: u64,
        hobbies: Vec<String>,
    }
    
    let json_chunks = [r#"{"name": "Ali"#,
                r#"ce", "age": 30#",
                r#", "hobbies": ["#,
                r#""reading", "co"#,
                r#"ding"]}"#];

    let p = JsonModemFacet<TestStruct>::new(...);
    for chunk in json_chunks {
        let partial = p.feed(chunk).unwrap();
        //  ^ &TestStruct
        println!("{partial:?}"); 
        // will print name: Ali on first iter, then name: Alice, age: 30, then name Alice, age 30, hobbies [], ... etc. 
    }
    let res: TestStruct = p.finish().unwrap();
    //  ^ final owned object
```

clone facet, facet-reflect, facet-json for reference and use them to determine how facet-json constructs values as a reference. include a spike on how to use facet safely and without allocating or cloning.

follow in the pattern of how JsonModemBuffers/JsonModemValues minimize allocations and wrap JsonModem, turning the parse event stream into higher level lending iterators. wrap JsonModem with JsonModemFacet<T> and do not allocate/clone T on iteration.
