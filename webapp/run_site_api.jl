const RUNNER_DEFAULT_SITE_API_PREFIX = "/api/site-payload"
const RUNNER_DEFAULT_SITE_API_HOST = "127.0.0.1"
const RUNNER_DEFAULT_SITE_API_PORT = 8081


runner_default_site_repo_root() = normpath(joinpath(@__DIR__, ".."))


function site_api_cli_usage()
    return """
Usage: julia --project=webapp webapp/run_site_api.jl [options]

Options:
    --repo-root PATH     Repository root to serve. Defaults to the MAMUT-routing checkout.
    --host HOST          Bind host. Default: $(RUNNER_DEFAULT_SITE_API_HOST)
    --port PORT          Bind port. Default: $(RUNNER_DEFAULT_SITE_API_PORT)
    --api-prefix PREFIX  Payload API prefix. Default: $(RUNNER_DEFAULT_SITE_API_PREFIX)
  --quiet              Disable HTTP.jl verbose request logging.
  -h, --help           Show this message and exit.
"""
end


function parse_site_api_cli_args(args::Vector{String})
    repo_root = runner_default_site_repo_root()
    host = RUNNER_DEFAULT_SITE_API_HOST
    port = RUNNER_DEFAULT_SITE_API_PORT
    api_prefix = RUNNER_DEFAULT_SITE_API_PREFIX
    verbose = true
    help = false

    index = 1
    while index <= length(args)
        arg = args[index]
        if arg == "-h" || arg == "--help"
            help = true
            index += 1
            continue
        end
        if arg == "--quiet"
            verbose = false
            index += 1
            continue
        end
        index == length(args) && throw(ArgumentError("Missing value for CLI option '$arg'"))
        value = args[index + 1]
        if arg == "--repo-root"
            repo_root = value
        elseif arg == "--host"
            host = value
        elseif arg == "--port"
            port = parse(Int, value)
        elseif arg == "--api-prefix"
            api_prefix = value
        else
            throw(ArgumentError("Unknown CLI option '$arg'"))
        end
        index += 2
    end

    return (
        repo_root=normpath(abspath(String(repo_root))),
        host=String(host),
        port=Int(port),
        api_prefix=String(api_prefix),
        verbose=verbose,
        help=help,
    )
end


function main(args::Vector{String}=ARGS)
    options = parse_site_api_cli_args(args)
    if options.help
        println(site_api_cli_usage())
        return nothing
    end
    include(joinpath(@__DIR__, "site_api.jl"))
    return Base.invokelatest(
        () -> getfield(@__MODULE__, :serve_site_api)(;
            repo_root=options.repo_root,
            host=options.host,
            port=options.port,
            api_prefix=options.api_prefix,
            verbose=options.verbose,
        )
    )
end


if abspath(PROGRAM_FILE) == @__FILE__
    try
        main()
    catch error
        if error isa ArgumentError
            println(stderr, sprint(showerror, error))
            println(stderr)
            println(stderr, site_api_cli_usage())
            exit(2)
        end
        println(stderr, sprint(showerror, error))
        println(stderr)
        println(stderr, "If this is a missing package error, run `julia --project=webapp -e 'using Pkg; Pkg.instantiate()'` first.")
        rethrow(error)
    end
end