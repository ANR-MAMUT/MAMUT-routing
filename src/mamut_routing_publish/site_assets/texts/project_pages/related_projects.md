# Related Projects

Several related projects are useful context for MAMUT-routing, even when they are not benchmark families shipped directly in the current tree.

They reinforce the central point of the ANR-MAMUT `MAMUT-routing` project: a benchmark is not only a set of instance files. It is a contract made of data provenance, objective semantics, numerical conventions, solution format, validation code, and maintenance policy.

## Combopt

[Combopt](http://combopt.org/tables/) and its [open repository](https://github.com/rogalski-wmii-uni-lodz-pl/vrp-benchmarks) provide one of the most useful community-maintained mirrors of classical VRP/VRPTW benchmark information. Its history section, GitHub repository, and overall design are direct inspiration for MAMUT-routing's benchmark-as-contract approach. Maintained by [Marek Rogalski](https://github.com/rogalski-wmii-uni-lodz-pl), it builds heavily on SINTEF's BKS culture and adds scripts and a checker-oriented workflow. It does not fully solve the reproducibility problem: many historical BKS files are missing or empty, the update policy is not always explicit, and the website itself is not open-source. Still, it is a useful community resource and a strong proof of concept for a curated benchmark repository.

## CVRPLib

[CVRPLib](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances) is the reference infrastructure for CVRP benchmarks and BKS. It is important for MAMUT-routing in two ways. First, it shows how useful a centralized curated benchmark library can be when it is widely trusted. Second, its newer VRPTW material overlaps with the classical Solomon and Homberger universe, so objective and cost conventions must be stated carefully whenever CVRPLib-derived VRPTW files are compared with `Sintef2008` or `Dimacs2021`.

## VRP-REP

[VRP-REP](http://www.vrp-rep.org/) was an ambitious attempt to provide a broader repository, checker, and specification platform for multiple VRP variants, including VRPTW. Its goal is close in spirit to MAMUT-routing: make benchmark data more structured and reusable. The project appears inactive today, which is a useful warning that benchmark infrastructure needs not only a schema, but also maintainable tooling, clear ownership, and an update process that survives beyond the initial publication.

## Dietmar Wolz's VRPTW Repository

Dietmar Wolz's [VRPTW repository](https://github.com/dietmarwo/VRPTW) is a smaller but relevant reproducibility-oriented project. It discusses precisely the ambiguities that motivate MAMUT-routing: cost-only versus hierarchical objectives, rounding policies, validation, and the difficulty of comparing solver results when route files and checkers are not shared consistently.
