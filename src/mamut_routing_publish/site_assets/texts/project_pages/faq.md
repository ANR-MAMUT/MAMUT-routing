# FAQ

This page collects short answers to common questions about contributing benchmark material and comparing MAMUT-routing conventions with other VRPTW sources.

## Contributions

`MAMUT-routing`, including its tooling, website, instance collection, and BKS collection, is open-source. Modifications, new benchmark instances, new problem classes, new objective functions, and other contributions are welcome.

Use the [GitHub repository](https://github.com/ANR-MAMUT/MAMUT-routing) to discuss or request changes, propose your help, fix issues, or upload new BKS files directly.

## CVRPLib, SINTEF, and DIMACS BKS

[CVRPLib](https://galgos.inf.puc-rio.br/cvrplib/en/instances) also lists Solomon and Gehring-Homberger VRPTW instances with BKS. However, the listed BKS appear to be computed on a `MonoCost` objective over floating-point Euclidean arc costs.

That differs from the historic [SINTEF](https://www.sintef.no/en/) [VRPTW benchmark](https://www.sintef.no/projectweb/top/vrptw/), which uses a hierarchical objective: first minimize the number of vehicles, then minimize travel cost.

It also differs from the newer [DIMACS](http://dimacs.rutgers.edu/) [VRPTW benchmark](http://dimacs.rutgers.edu/index.php/programs/challenge/vrp/vrptw/), which uses the same mono-cost objective but on scaled integerized arc costs. This integerization changes the optimization landscape, so BKS values and routes are only comparable when the complete benchmark contract matches.
