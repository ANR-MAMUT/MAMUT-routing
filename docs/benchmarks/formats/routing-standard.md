# Routing Standard

[Read the MAMUT-routing Standard Specification, version 0.1 (PDF)](../../specifications/mamut-routing-standard-0.1.pdf)

The Standard defines how to read numerical inputs for static and time-dependent routing benchmarks, evaluate routes and reproduce the exact cost recorded in a best-known solution. A manifest pins the numerical inputs. The result records the manifest digest, the evaluation profile and the cost as a fraction.

**Specification version and benchmark edition.** In a result, `metadata.standard.specification` identifies the rules as `mamut-routing/0.1`. The separate `benchmark_revision` field identifies the edition of the instance variant, such as `r1`. The edition guide shows how to replay a published result. The format guides describe the benchmark files, and the Python API reference documents the library models and functions. [Edition r1 migration and replay](edition-r1.md) · [Formats](index.md) · [Python API reference](../../reference/api/index.md)

## Worked examples

| Example | What to check | Files |
| --- | --- | --- |
| Static routing | The exact sum of 3 binary64 arc costs displays as `0.6`. The result gives the numerator and denominator. | [Instance][static-instance] · [Manifest][static-manifest] · [Result][static-result] |
| Time-dependent routing | Each route has a minimum duration and an earliest departure that attains it. Including both vehicle charges gives an exact total of `79/6`. | [Instance][td-instance] · [Arc functions][td-arcs] · [Manifest][td-manifest] · [Result][td-result] |

## Source and attribution

Adrien Pichon, Florian Rascoussier, Romain Billot, Lina Fahed, Alexandru-Liviu Olteanu, Marc Sevaux and Christine Solnon authored the specification. Its text, figures and PDF are distributed under CC BY 4.0. The companion code and examples use the MIT License. [Version 0.1 source][source] · [CC BY 4.0][text-licence] · [MIT License][code-licence]

[source]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/tree/d01339d5bd655fe3a88f8b2468ffb7da90f088aa
[text-licence]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/LICENSE
[code-licence]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/LICENSE-CODE
[static-instance]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/example-instance.json
[static-manifest]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/example-instance.manifest.json
[static-result]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/example-result.json
[td-instance]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/example-td-instance.json
[td-arcs]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/example-td.atf.json
[td-manifest]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/example-td-instance.manifest.json
[td-result]: https://github.com/ANR-MAMUT/MAMUT-routing-standard-specification/blob/d01339d5bd655fe3a88f8b2468ffb7da90f088aa/example-td-result.json
