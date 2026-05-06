@isdefined(load_json_site_payload) || include(joinpath(@__DIR__, "io-json-vrp.jl"))

using OpenStreetMapX
using OSMToolset
using Hygese

@isdefined(MAMUT_OSM_GENERATION_HELPERS_LOADED) || include(joinpath(@__DIR__, "osm_generation.jl"))


const DEFAULT_SITE_API_PREFIX = "/api/site-payload"
const DEFAULT_SITE_OUTPUT_ROOT = "dist"
const DEFAULT_SITE_PAYLOAD_ROOT = "site-payloads"
const DEFAULT_SITE_API_HOST = "127.0.0.1"
const DEFAULT_SITE_API_PORT = 8081
const WORKBENCH_CACHE_ENDPOINT_TOLERANCE_METERS = 250.0
const WORKBENCH_MAP_CACHE = Dict{String,Any}()
const REPO_ARTIFACT_ROOT_ENTRIES = Set([
    "LICENSE",
    "benchmarks",
])



default_site_repo_root() = normpath(joinpath(@__DIR__, ".."))


function canonical_site_repo_root(repo_root::AbstractString=default_site_repo_root())
    return normpath(abspath(String(repo_root)))
end


function normalize_site_route_path(route_path::AbstractString)
    candidate = replace(strip(String(route_path)), '\\' => '/')
    isempty(candidate) && return "/"
    candidate == "index.json" && return "/"
    endswith(candidate, "/index.json") && (candidate = candidate[1:end - length("/index.json")])
    startswith(candidate, "/") || (candidate = "/" * candidate)

    segments = filter(!isempty, split(candidate, '/'))
    isempty(segments) && return "/"
    return "/" * join(segments, "/") * "/"
end


function site_payload_relative_path(route_path::AbstractString)
    normalized = normalize_site_route_path(route_path)
    normalized == "/" && return joinpath(DEFAULT_SITE_OUTPUT_ROOT, DEFAULT_SITE_PAYLOAD_ROOT, "index.json")
    inner_path = normalized[2:end - 1]
    return joinpath(DEFAULT_SITE_OUTPUT_ROOT, DEFAULT_SITE_PAYLOAD_ROOT, split(inner_path, "/")..., "index.json")
end


function site_payload_file_for_route(repo_root::AbstractString, route_path::AbstractString)
    normalized = normalize_site_route_path(route_path)
    payload_path = joinpath(canonical_site_repo_root(repo_root), site_payload_relative_path(normalized))
    isfile(payload_path) || throw(ArgumentError("No generated site payload found for route '$normalized' at '$payload_path'"))
    return payload_path
end


function load_site_payload_for_route(repo_root::AbstractString, route_path::AbstractString)
    payload_path = site_payload_file_for_route(repo_root, route_path)
    return load_json_site_payload(payload_path)
end


function site_payload_summary(repo_root::AbstractString, route_path::AbstractString)
    normalized = normalize_site_route_path(route_path)
    payload_path = site_payload_file_for_route(repo_root, normalized)
    model = load_json_site_payload(payload_path)
    return (
        route_path=normalized,
        payload_path=payload_path,
        payload_kind=String(getfield(model, :payload_kind)),
        model_type=string(typeof(model)),
    )
end


function render_site_payload_json(repo_root::AbstractString, route_path::AbstractString; indent::Int=2, sort_keys::Bool=false)
    model = load_site_payload_for_route(repo_root, route_path)
    return custom_json_encode(model; indent=indent, sort_keys=sort_keys)
end


function percent_decode(value::AbstractString; plus_as_space::Bool=true)
    bytes = UInt8[]
    index = firstindex(value)
    while index <= lastindex(value)
        current = value[index]
        if current == '%'
            next_1 = nextind(value, index)
            next_2 = nextind(value, next_1)
            next_2 <= lastindex(value) || throw(ArgumentError("Malformed percent-encoded string"))
            hex_value = value[next_1:next_2]
            push!(bytes, parse(UInt8, hex_value; base=16))
            index = nextind(value, next_2)
            continue
        end
        push!(bytes, plus_as_space && current == '+' ? UInt8(' ') : codeunit(value, index))
        index = nextind(value, index)
    end
    return String(bytes)
end


function parse_query_params(query::AbstractString)
    params = Dict{String,String}()
    isempty(query) && return params
    for pair in split(query, '&')
        isempty(pair) && continue
        key_value = split(pair, '='; limit=2)
        key = percent_decode(key_value[1])
        value = length(key_value) == 2 ? percent_decode(key_value[2]) : ""
        params[key] = value
    end
    return params
end


function split_request_target(target::AbstractString)
    pieces = split(String(target), '?'; limit=2)
    path = pieces[1]
    query = length(pieces) == 2 ? pieces[2] : ""
    return path, query
end


function normalize_site_request_path(path::AbstractString)
    candidate = replace(percent_decode(String(path); plus_as_space=false), '\\' => '/')
    isempty(candidate) && return "/"
    startswith(candidate, "/") || (candidate = "/" * candidate)

    keep_trailing_slash = endswith(candidate, "/")
    segments = String[]
    for segment in split(candidate, '/')
        isempty(segment) && continue
        segment == "." && continue
        segment == ".." && throw(ArgumentError("Path traversal is not allowed in site requests"))
        push!(segments, segment)
    end

    isempty(segments) && return "/"
    normalized = "/" * join(segments, "/")
    return keep_trailing_slash ? normalized * "/" : normalized
end


function is_repo_artifact_relative_path(relative_path::AbstractString)
    normalized = replace(String(relative_path), '\\' => '/')
    isempty(normalized) && return false
    first_segment = split(normalized, '/'; limit=2)[1]
    return first_segment in REPO_ARTIFACT_ROOT_ENTRIES
end


function site_public_file_for_target(repo_root::AbstractString, target::AbstractString)
    path, _ = split_request_target(target)
    normalized_request_path = normalize_site_request_path(path)

    relative_candidates = String[]
    if normalized_request_path == "/"
        push!(relative_candidates, "index.html")
    else
        relative_request = normalized_request_path[2:end]
        if endswith(normalized_request_path, "/")
            relative_request = relative_request[1:end - 1]
            push!(relative_candidates, joinpath(split(relative_request, "/")..., "index.html"))
        else
            relative_path = joinpath(split(relative_request, "/")...)
            push!(relative_candidates, relative_path)
            basename(relative_path) == splitext(basename(relative_path))[1] && push!(relative_candidates, joinpath(relative_path, "index.html"))
        end
    end

    resolved_repo_root = canonical_site_repo_root(repo_root)
    repo_root_with_sep = resolved_repo_root * Base.Filesystem.path_separator
    resolved_site_root = normpath(joinpath(resolved_repo_root, DEFAULT_SITE_OUTPUT_ROOT))
    site_root_with_sep = resolved_site_root * Base.Filesystem.path_separator
    for relative_candidate in relative_candidates
        absolute_site_candidate = normpath(joinpath(resolved_site_root, relative_candidate))
        if (absolute_site_candidate == resolved_site_root || startswith(absolute_site_candidate, site_root_with_sep)) && isfile(absolute_site_candidate)
            return (
                request_path=normalized_request_path,
                relative_path=relpath(absolute_site_candidate, resolved_repo_root),
                absolute_path=absolute_site_candidate,
            )
        end

        is_repo_artifact_relative_path(relative_candidate) || continue
        absolute_repo_candidate = normpath(joinpath(resolved_repo_root, relative_candidate))
        (absolute_repo_candidate == resolved_repo_root || startswith(absolute_repo_candidate, repo_root_with_sep)) || continue
        isfile(absolute_repo_candidate) || continue
        return (
            request_path=normalized_request_path,
            relative_path=relative_candidate,
            absolute_path=absolute_repo_candidate,
        )
    end

    throw(ArgumentError("No public site file found for request path '$normalized_request_path'"))
end


function site_public_content_type(filepath::AbstractString)
    extension = lowercase(splitext(String(filepath))[2])
    extension == ".html" && return "text/html; charset=utf-8"
    extension == ".css" && return "text/css; charset=utf-8"
    extension == ".js" && return "text/javascript; charset=utf-8"
    extension == ".svg" && return "image/svg+xml"
    extension == ".png" && return "image/png"
    extension == ".jpg" && return "image/jpeg"
    extension == ".jpeg" && return "image/jpeg"
    extension == ".json" && return "application/json; charset=utf-8"
    extension == ".vrp" && return "text/plain; charset=utf-8"
    extension == ".txt" && return "text/plain; charset=utf-8"
    extension == ".md" && return "text/markdown; charset=utf-8"
    return "application/octet-stream"
end


function read_site_public_file(repo_root::AbstractString, target::AbstractString)
    resolved = site_public_file_for_target(repo_root, target)
    return (
        request_path=resolved.request_path,
        relative_path=resolved.relative_path,
        absolute_path=resolved.absolute_path,
        content_type=site_public_content_type(resolved.absolute_path),
        body=read(resolved.absolute_path),
    )
end


function extract_site_payload_route(target::AbstractString; api_prefix::AbstractString=DEFAULT_SITE_API_PREFIX)
    path, query = split_request_target(target)

    if path == api_prefix
        params = parse_query_params(query)
        return haskey(params, "route") ? normalize_site_route_path(params["route"]) : "/"
    end

    nested_prefix = api_prefix * "/"
    if startswith(path, nested_prefix)
        suffix = path[length(nested_prefix) + 1:end]
        return normalize_site_route_path(suffix)
    end

    return nothing
end


function load_http_module()
    if !isdefined(@__MODULE__, :HTTP)
        try
            @eval import HTTP
        catch error
            throw(ArgumentError("HTTP.jl is required to run the site API server: $(sprint(showerror, error))"))
        end
    end
    return Base.invokelatest(() -> getfield(@__MODULE__, :HTTP))
end


site_api_headers() = [
    "Content-Type" => "application/json; charset=utf-8",
    "Cache-Control" => "no-store",
    "Access-Control-Allow-Origin" => "*",
]


site_static_headers(content_type::AbstractString) = [
    "Content-Type" => String(content_type),
    "Cache-Control" => "no-store",
]


function site_api_error_body(code::AbstractString, message::AbstractString)
    return custom_json_encode(Dict("error" => String(code), "message" => String(message)); indent=2, sort_keys=true) * "\n"
end


function site_api_json_response(status::Integer, payload)
    http = load_http_module()
    return http.Response(Int(status), site_api_headers(), custom_json_encode(payload; indent=2, sort_keys=true) * "\n")
end


function site_api_payload_get(payload, key::AbstractString, default=nothing)
    haskey(payload, key) && return payload[key]
    symbol_key = Symbol(key)
    haskey(payload, symbol_key) && return payload[symbol_key]
    return default
end


function workbench_parse_routes_from_sol(sol_text::AbstractString)
    routes = Vector{Vector{Int}}()
    for line in split(String(sol_text), '\n')
        match_obj = match(r"^\s*Route\s*#\d+\s*:\s*(.*)$"i, line)
        match_obj === nothing && continue
        stops = parse.(Int, filter(!isempty, split(strip(match_obj.captures[1]))))
        push!(routes, stops)
    end
    isempty(routes) && throw(ArgumentError("No routes found in solution text"))
    return routes
end


function workbench_parse_routes(payload)
    routes_payload = site_api_payload_get(payload, "routes", nothing)
    if routes_payload !== nothing
        routes_payload isa AbstractVector || throw(ArgumentError("Expected 'routes' to be an array of routes"))
        return [Int.(collect(route)) for route in routes_payload]
    end

    sol_text = site_api_payload_get(payload, "solText", nothing)
    sol_text === nothing && throw(ArgumentError("Request must contain either 'routes' or 'solText'"))
    return workbench_parse_routes_from_sol(String(sol_text))
end


function workbench_node_id(node)
    raw_value = site_api_payload_get(node, "instance_node_id", nothing)
    raw_value === nothing && return nothing
    return Int(raw_value)
end


function workbench_graph_vertex_id(node)
    raw_value = site_api_payload_get(node, "graph_vertex_id", nothing)
    raw_value === nothing && return nothing
    return Int(raw_value)
end


function workbench_node_coordinates_map(meta)
    nodes = site_api_payload_get(meta, "nodes", nothing)
    nodes isa AbstractVector || throw(ArgumentError("Request meta is missing its nodes list"))

    coordinates = Dict{Int,Vector{Float64}}()
    for node in nodes
        node_id = workbench_node_id(node)
        node_id === nothing && continue
        point = workbench_node_coordinates(node)
        point === nothing && continue
        coordinates[node_id] = point
    end

    isempty(coordinates) && throw(ArgumentError("Request meta does not expose any previewable node coordinates"))
    return coordinates
end


function workbench_graph_vertex_id_map(meta)
    nodes = site_api_payload_get(meta, "nodes", nothing)
    nodes isa AbstractVector || return Dict{Int,Int}()

    mapping = Dict{Int,Int}()
    for node in nodes
        node_id = workbench_node_id(node)
        graph_vertex_id = workbench_graph_vertex_id(node)
        (node_id === nothing || graph_vertex_id === nothing) && continue
        mapping[node_id] = graph_vertex_id
    end
    return mapping
end


function workbench_node_lonlat(node)
    poi_lon = site_api_payload_get(node, "poi_lon", nothing)
    poi_lat = site_api_payload_get(node, "poi_lat", nothing)
    (poi_lon === nothing || poi_lat === nothing) && return nothing
    return (lon=Float64(poi_lon), lat=Float64(poi_lat))
end


function workbench_current_graph_vertex_id_map(meta, map_data)
    nodes = site_api_payload_get(meta, "nodes", nothing)
    nodes isa AbstractVector || return Dict{Int,Int}()

    ref_lla = OpenStreetMapX.center(map_data.bounds)
    node_index = NodeSpatIndex(map_data, ref_lla)
    mapping = Dict{Int,Int}()
    for node in nodes
        node_id = workbench_node_id(node)
        lonlat = workbench_node_lonlat(node)
        (node_id === nothing || lonlat === nothing) && continue
        _, osm_id = findnode(node_index, LLA(lonlat.lat, lonlat.lon))
        if osm_id != 0 && haskey(map_data.v, osm_id)
            mapping[node_id] = map_data.v[osm_id]
        end
    end
    return mapping
end


function workbench_node_edge_cache_key(from_node::Int, to_node::Int)
    return "node:$(from_node)_$(to_node)"
end


function workbench_map_option_candidates(only_intersections::Bool, trim_to_connected_graph::Bool)
    options = Tuple{Bool,Bool}[
        (only_intersections, trim_to_connected_graph),
        (false, trim_to_connected_graph),
        (only_intersections, false),
        (false, false),
    ]
    seen = Set{Tuple{Bool,Bool}}()
    unique_options = Tuple{Bool,Bool}[]
    for option in options
        option in seen && continue
        push!(seen, option)
        push!(unique_options, option)
    end
    return unique_options
end


function workbench_route_map_candidates(
    repo_root::AbstractString,
    meta,
    meta_file_path::AbstractString,
    only_intersections::Bool,
    trim_to_connected_graph::Bool,
)
    osm_path = workbench_resolve_source_osm_path(repo_root, meta, meta_file_path)
    candidates = Any[]
    for (oi, ttcg) in workbench_map_option_candidates(only_intersections, trim_to_connected_graph)
        map_data = try
            workbench_get_map_data_cached(osm_path; only_intersections=oi, trim_to_connected_graph=ttcg)
        catch error
            if error isa ArgumentError || error isa SystemError
                continue
            end
            rethrow(error)
        end
        push!(candidates, (
            only_intersections=oi,
            trim_to_connected_graph=ttcg,
            map_data=map_data,
            graph_vertex_ids=workbench_current_graph_vertex_id_map(meta, map_data),
        ))
    end
    return candidates
end


function workbench_route_demand(route::AbstractVector, meta)
    nodes = site_api_payload_get(meta, "nodes", nothing)
    nodes isa AbstractVector || return 0

    demands = Dict{Int,Int}()
    for node in nodes
        node_id = workbench_node_id(node)
        node_id === nothing && continue
        demands[node_id] = Int(site_api_payload_get(node, "demand", 0))
    end
    return sum(get(demands, Int(stop), 0) for stop in route; init=0)
end


function workbench_cache_key(osm_path::AbstractString, only_intersections::Bool, trim_to_connected_graph::Bool)
    return "$(String(osm_path))|oi=$(only_intersections)|trim=$(trim_to_connected_graph)"
end


function workbench_ensure_bounds_from_nodes!(osm_path::AbstractString)
    osm_path_string = String(osm_path)
    text = read(osm_path_string, String)
    occursin(r"<bounds\b", text) && return

    lats = Float64[]
    lons = Float64[]
    for match_obj in eachmatch(r"<node\b[^>]*\blat=\"([^\"]+)\"[^>]*\blon=\"([^\"]+)\"", text)
        push!(lats, parse(Float64, match_obj.captures[1]))
        push!(lons, parse(Float64, match_obj.captures[2]))
    end
    isempty(lats) && throw(ArgumentError("OSM file '$(osm_path_string)' contains no nodes; cannot derive bounds"))

    minlat, maxlat = extrema(lats)
    minlon, maxlon = extrema(lons)
    ensure_osm_has_bounds!(osm_path_string, minlat, minlon, maxlat, maxlon)
end


function workbench_get_map_data_cached(osm_path::AbstractString; only_intersections::Bool=true, trim_to_connected_graph::Bool=true)
    resolved_path = normpath(abspath(String(osm_path)))
    key = workbench_cache_key(resolved_path, only_intersections, trim_to_connected_graph)
    haskey(WORKBENCH_MAP_CACHE, key) && return WORKBENCH_MAP_CACHE[key]

    workbench_ensure_bounds_from_nodes!(resolved_path)

    fallbacks = Tuple{Bool,Bool}[
        (only_intersections, trim_to_connected_graph),
        (only_intersections, false),
        (false, trim_to_connected_graph),
        (false, false),
    ]

    seen = Set{Tuple{Bool,Bool}}()
    for (oi, ttcg) in fallbacks
        (oi, ttcg) in seen && continue
        push!(seen, (oi, ttcg))
        try
            map_data = get_map_data(resolved_path; use_cache=false, only_intersections=oi, trim_to_connected_graph=ttcg)
            WORKBENCH_MAP_CACHE[workbench_cache_key(resolved_path, oi, ttcg)] = map_data
            WORKBENCH_MAP_CACHE[key] = map_data
            return map_data
        catch error
            if error isa ArgumentError && occursin("empty collection", String(error))
                continue
            end
            rethrow(error)
        end
    end

    throw(ArgumentError("OSM file '$(resolved_path)' produced an empty road graph"))
end


function workbench_segment_coords(map_data, from_vertex::Int, to_vertex::Int, metric::AbstractString)
    (1 <= from_vertex <= length(map_data.n)) || throw(ArgumentError("Graph vertex id $(from_vertex) is out of bounds for this map"))
    (1 <= to_vertex <= length(map_data.n)) || throw(ArgumentError("Graph vertex id $(to_vertex) is out of bounds for this map"))

    from_osm_id = map_data.n[from_vertex]
    to_osm_id = map_data.n[to_vertex]
    node_route = if metric == "fastest"
        fastest_route(map_data, from_osm_id, to_osm_id)[1]
    elseif metric == "shortest"
        shortest_route(map_data, from_osm_id, to_osm_id)[1]
    else
        throw(ArgumentError("Unsupported road metric '$(metric)'"))
    end

    coordinates = Vector{Vector{Float64}}()
    for node_id in node_route
        lla = LLA(map_data.nodes[node_id], map_data.bounds)
        push!(coordinates, [lla.lon, lla.lat])
    end
    return coordinates
end


function workbench_load_road_cache(meta_file_path::AbstractString, metric::AbstractString)
    cache = Dict{String,Vector{Vector{Float64}}}()
    isfile(meta_file_path) || return cache

    meta_payload = load_json_from_file(meta_file_path)
    road_cache = site_api_payload_get(meta_payload, "road_cache", nothing)
    road_cache isa AbstractDict || return cache
    metric_cache = site_api_payload_get(road_cache, String(metric), nothing)
    metric_cache isa AbstractDict || return cache

    for (key, value) in pairs(metric_cache)
        cache[String(key)] = [Float64.(collect(point)) for point in value]
    end
    return cache
end


function workbench_save_road_cache(meta_file_path::AbstractString, metric::AbstractString, edge_cache::Dict{String,Vector{Vector{Float64}}})
    isfile(meta_file_path) || return

    meta_payload = load_json_from_file(meta_file_path)
    road_cache = site_api_payload_get(meta_payload, "road_cache", nothing)
    road_cache isa AbstractDict || (road_cache = Dict{String,Any}())
    meta_payload["road_cache"] = road_cache
    road_cache[String(metric)] = Dict(key => value for (key, value) in pairs(edge_cache))
    save_json_to_file(meta_payload, meta_file_path; indent=4, sort_keys=false)
end


function workbench_resolve_repo_relative_path(repo_root::AbstractString, relative_path::AbstractString)
    normalized_relative = replace(strip(String(relative_path)), '\\' => '/')
    isempty(normalized_relative) && throw(ArgumentError("Expected a non-empty repository-relative path"))
    startswith(normalized_relative, "/") && throw(ArgumentError("Expected a repository-relative path, got '$(normalized_relative)'"))

    resolved_repo_root = canonical_site_repo_root(repo_root)
    absolute_path = normpath(joinpath(resolved_repo_root, split(normalized_relative, "/")...))
    repo_root_with_sep = resolved_repo_root * Base.Filesystem.path_separator
    (absolute_path == resolved_repo_root || startswith(absolute_path, repo_root_with_sep)) || throw(ArgumentError("Path traversal is not allowed in workbench render requests"))
    isfile(absolute_path) || throw(ArgumentError("No file found at repository path '$(normalized_relative)'"))
    return absolute_path
end


function workbench_resolve_source_osm_path(repo_root::AbstractString, meta, meta_file_path::AbstractString)
    source_osm_file = site_api_payload_get(meta, "source_osm_file", nothing)
    source_osm_file === nothing && throw(ArgumentError("Sidecar '$(meta_file_path)' is missing 'source_osm_file'"))
    source_osm_path = String(source_osm_file)

    isabspath(source_osm_path) && isfile(source_osm_path) && return normpath(source_osm_path)

    candidate_paths = String[
        normpath(joinpath(dirname(meta_file_path), source_osm_path)),
        normpath(joinpath(canonical_site_repo_root(repo_root), source_osm_path)),
    ]
    unique!(candidate_paths)

    for candidate_path in candidate_paths
        isfile(candidate_path) && return candidate_path
    end

    throw(ArgumentError("Unable to resolve source OSM file '$(source_osm_path)' for sidecar '$(meta_file_path)'"))
end


function workbench_cached_route_segment(
    edge_cache::Dict{String,Vector{Vector{Float64}}},
    graph_vertex_maps::AbstractVector,
    from_node::Int,
    to_node::Int,
    from_coordinates,
    to_coordinates,
)
    segment = workbench_cached_node_segment(edge_cache, from_node, to_node, from_coordinates, to_coordinates)
    segment !== nothing && return segment

    for graph_vertex_ids in graph_vertex_maps
        graph_vertex_ids isa AbstractDict || continue
        (haskey(graph_vertex_ids, from_node) && haskey(graph_vertex_ids, to_node)) || continue
        segment = workbench_cached_segment(edge_cache, graph_vertex_ids[from_node], graph_vertex_ids[to_node], from_coordinates, to_coordinates)
        segment !== nothing && return segment
    end
    return nothing
end


function workbench_candidate_route_segment(
    map_candidates::AbstractVector,
    from_node::Int,
    to_node::Int,
    from_coordinates,
    to_coordinates,
    metric::AbstractString,
)
    for candidate in map_candidates
        graph_vertex_ids = candidate.graph_vertex_ids
        graph_vertex_ids isa AbstractDict || continue
        (haskey(graph_vertex_ids, from_node) && haskey(graph_vertex_ids, to_node)) || continue
        candidate_segment = try
            workbench_segment_coords(candidate.map_data, graph_vertex_ids[from_node], graph_vertex_ids[to_node], metric)
        catch error
            if error isa ArgumentError || error isa KeyError
                nothing
            else
                rethrow(error)
            end
        end
        candidate_segment === nothing && continue
        workbench_cached_segment_matches_endpoints(candidate_segment, from_coordinates, to_coordinates) || continue
        return candidate_segment
    end
    return nothing
end


function workbench_fill_missing_route_segments!(
    segments::Vector{Any},
    full_route::Vector{Int},
    node_coordinates::Dict{Int,Vector{Float64}},
    edge_cache::Dict{String,Vector{Vector{Float64}}},
    map_candidates::AbstractVector,
    metric::AbstractString,
)
    missing_edges = Tuple{Int,Int}[]
    seen_edges = Set{Tuple{Int,Int}}()
    for index in eachindex(segments)
        segments[index] !== nothing && continue
        edge = (full_route[index], full_route[index + 1])
        edge in seen_edges && continue
        push!(seen_edges, edge)
        push!(missing_edges, edge)
    end
    isempty(missing_edges) && return false

    resolved_segments = Vector{Any}(undef, length(missing_edges))
    Threads.@threads for index in eachindex(missing_edges)
        from_node, to_node = missing_edges[index]
        resolved_segments[index] = workbench_candidate_route_segment(
            map_candidates,
            from_node,
            to_node,
            node_coordinates[from_node],
            node_coordinates[to_node],
            metric,
        )
    end

    used_live_routing = false
    for (index, edge) in enumerate(missing_edges)
        segment = resolved_segments[index]
        segment === nothing && continue
        from_node, to_node = edge
        edge_cache[workbench_node_edge_cache_key(from_node, to_node)] = segment
        used_live_routing = true
    end

    for index in eachindex(segments)
        segments[index] !== nothing && continue
        from_node = full_route[index]
        to_node = full_route[index + 1]
        segments[index] = workbench_cached_node_segment(edge_cache, from_node, to_node, node_coordinates[from_node], node_coordinates[to_node])
    end

    return used_live_routing
end


function workbench_live_route_coordinates(repo_root::AbstractString, meta, meta_file_path::AbstractString, route::AbstractVector, metric::AbstractString, edge_cache::Dict{String,Vector{Vector{Float64}}})
    metric in ("shortest", "fastest") || throw(ArgumentError("Live road rendering only supports 'shortest' and 'fastest' metrics"))

    node_coordinates = workbench_node_coordinates_map(meta)
    saved_graph_vertex_ids = workbench_graph_vertex_id_map(meta)
    depot_node_id = Int(site_api_payload_get(meta, "depot_instance_node_id", 1))
    full_route = [depot_node_id; Int.(collect(route)); depot_node_id]
    length(full_route) >= 2 || throw(ArgumentError("Routes must include at least one customer stop"))
    all(haskey(node_coordinates, node_id) for node_id in full_route) || throw(ArgumentError("Route references unknown instance node ids"))

    map_options = site_api_payload_get(meta, "map_options", Dict{String,Any}())
    only_intersections = Bool(site_api_payload_get(map_options, "only_intersections", true))
    trim_to_connected_graph = Bool(site_api_payload_get(map_options, "trim_to_connected_graph", true))

    map_candidates_ref = Ref{Any}(nothing)
    map_loaded = Ref(false)
    map_unavailable = Ref(false)

    function ensure_map_loaded!()
        (map_loaded[] || map_unavailable[]) && return
        try
            map_candidates_ref[] = workbench_route_map_candidates(
                repo_root,
                meta,
                meta_file_path,
                only_intersections,
                trim_to_connected_graph,
            )
            isempty(map_candidates_ref[]) && throw(ArgumentError("No usable OSM road graph was available"))
            map_loaded[] = true
        catch error
            if error isa ArgumentError || error isa SystemError
                map_unavailable[] = true
                return
            end
            rethrow(error)
        end
    end

    route_coordinates = Vector{Vector{Float64}}()
    used_cache = false
    used_live_routing = false
    used_straight_fallback = false
    cache_miss_count = 0
    straight_fallback_count = 0

    edge_count = length(full_route) - 1
    segments = Vector{Any}(undef, edge_count)
    fill!(segments, nothing)
    saved_graph_vertex_maps = Any[saved_graph_vertex_ids]
    for index in 1:edge_count
        from_node = full_route[index]
        to_node = full_route[index + 1]
        from_coordinates = node_coordinates[from_node]
        to_coordinates = node_coordinates[to_node]
        segment = workbench_cached_route_segment(edge_cache, saved_graph_vertex_maps, from_node, to_node, from_coordinates, to_coordinates)
        if segment !== nothing
            segments[index] = segment
            used_cache = true
        end
    end

    if any(segment -> segment === nothing, segments)
        ensure_map_loaded!()
        map_candidates = map_loaded[] ? map_candidates_ref[] : Any[]

        if map_loaded[]
            current_graph_vertex_maps = [candidate.graph_vertex_ids for candidate in map_candidates]
            for index in 1:edge_count
                segments[index] !== nothing && continue
                from_node = full_route[index]
                to_node = full_route[index + 1]
                from_coordinates = node_coordinates[from_node]
                to_coordinates = node_coordinates[to_node]
                segment = workbench_cached_route_segment(edge_cache, current_graph_vertex_maps, from_node, to_node, from_coordinates, to_coordinates)
                if segment !== nothing
                    segments[index] = segment
                    used_cache = true
                end
            end

            missing_before_live = count(segment -> segment === nothing, segments)
            if missing_before_live > 0
                cache_miss_count += missing_before_live
                used_live_routing |= workbench_fill_missing_route_segments!(
                    segments,
                    full_route,
                    node_coordinates,
                    edge_cache,
                    map_candidates,
                    metric,
                )
            end
        else
            cache_miss_count += count(segment -> segment === nothing, segments)
        end
    end

    for index in 1:edge_count
        segment = segments[index]
        if segment === nothing
            segment = workbench_straight_segment(node_coordinates, full_route[index], full_route[index + 1])
            used_straight_fallback = true
            straight_fallback_count += 1
        end

        start_index = index == 1 ? 1 : 2
        append!(route_coordinates, segment[start_index:end])
    end

    render_mode = if used_straight_fallback && (used_cache || used_live_routing)
        "mixed"
    elseif used_live_routing && used_cache
        "mixed"
    elseif used_live_routing
        "road"
    elseif used_cache
        "cached_road"
    else
        "straight_line"
    end

    return route_coordinates, render_mode, cache_miss_count, used_live_routing, used_straight_fallback, straight_fallback_count
end


function workbench_bootstrap_edge_cache_from_meta(meta, metric::AbstractString)
    cache = Dict{String,Vector{Vector{Float64}}}()
    road_cache = site_api_payload_get(meta, "road_cache", nothing)
    road_cache isa AbstractDict || return cache
    metric_cache = site_api_payload_get(road_cache, String(metric), nothing)
    metric_cache isa AbstractDict || return cache
    for (key, value) in pairs(metric_cache)
        cache[String(key)] = [Float64.(collect(point)) for point in value]
    end
    return cache
end


function workbench_render_routes_with_live_routing(
    repo_root::AbstractString,
    meta,
    routes::AbstractVector,
    metric::AbstractString;
    meta_file_path::AbstractString="",
    persist_cache::Bool=false,
    meta_path_label::AbstractString="",
)
    metric in ("shortest", "fastest") || throw(ArgumentError("Live road rendering only supports 'shortest' and 'fastest' metrics"))

    edge_cache = if persist_cache && !isempty(meta_file_path) && isfile(meta_file_path)
        workbench_load_road_cache(meta_file_path, metric)
    else
        workbench_bootstrap_edge_cache_from_meta(meta, metric)
    end
    initial_cache_size = length(edge_cache)

    features = Any[]
    used_cache = false
    used_live_routing = false
    straight_fallback_count = 0
    cache_miss_count = 0

    for (route_index, route) in enumerate(routes)
        coordinates, render_mode, route_cache_misses, route_used_live_routing, route_used_straight_fallback, route_straight_fallback_count = workbench_live_route_coordinates(
            repo_root,
            meta,
            meta_file_path,
            route,
            metric,
            edge_cache,
        )
        route_used_live_routing && (used_live_routing = true)
        route_used_straight_fallback && (straight_fallback_count += route_straight_fallback_count)
        route_cache_misses < length(route) + 1 && (used_cache = true)
        cache_miss_count += route_cache_misses
        push!(features, Dict(
            "type" => "Feature",
            "geometry" => Dict(
                "type" => "LineString",
                "coordinates" => coordinates,
            ),
            "properties" => Dict(
                "route_index" => route_index,
                "stops" => length(route),
                "load" => workbench_route_demand(route, meta),
                "metric" => metric,
                "render_mode" => render_mode,
            ),
        ))
    end

    cache_persisted = false
    if persist_cache && used_live_routing && cache_miss_count > 0 && !isempty(meta_file_path) && isfile(meta_file_path)
        workbench_save_road_cache(meta_file_path, metric, edge_cache)
        cache_persisted = true
    end

    render_mode = if straight_fallback_count > 0 && (used_cache || used_live_routing)
        "mixed"
    elseif used_live_routing && used_cache
        "mixed"
    elseif used_live_routing
        "road"
    elseif used_cache
        "cached_road"
    else
        "straight_line"
    end

    new_cache_entry_count = length(edge_cache) - initial_cache_size

    summary = Dict{String,Any}(
        "metric" => metric,
        "route_count" => length(routes),
        "render_mode" => render_mode,
        "used_cache" => used_cache,
        "cache_miss_count" => cache_miss_count,
        "straight_fallback_count" => straight_fallback_count,
        "cache_persisted" => cache_persisted,
        "new_cache_entry_count" => new_cache_entry_count,
        "meta_path" => String(meta_path_label),
    )

    return Dict(
        "ok" => true,
        "geojson" => Dict(
            "type" => "FeatureCollection",
            "features" => features,
        ),
        "summary" => summary,
    )
end


function workbench_render_routes_from_meta_path(repo_root::AbstractString, meta_path::AbstractString, routes::AbstractVector, metric::AbstractString)
    metric in ("shortest", "fastest") || throw(ArgumentError("Persistent benchmark rendering only supports 'shortest' and 'fastest' metrics"))

    meta_file_path = workbench_resolve_repo_relative_path(repo_root, meta_path)
    meta = load_json_from_file(meta_file_path)
    return workbench_render_routes_with_live_routing(
        repo_root,
        meta,
        routes,
        metric;
        meta_file_path=meta_file_path,
        persist_cache=true,
        meta_path_label=meta_path,
    )
end


function workbench_is_lonlat_point(point::AbstractVector)
    length(point) >= 2 || return false
    return abs(Float64(point[1])) <= 180.0 && abs(Float64(point[2])) <= 90.0
end


function workbench_point_distance_meters(first_point::AbstractVector, second_point::AbstractVector)
    if workbench_is_lonlat_point(first_point) && workbench_is_lonlat_point(second_point)
        mean_lat = (Float64(first_point[2]) + Float64(second_point[2])) / 2
        lon_scale = 111_320.0 * cosd(mean_lat)
        lat_scale = 111_320.0
        return hypot((Float64(first_point[1]) - Float64(second_point[1])) * lon_scale, (Float64(first_point[2]) - Float64(second_point[2])) * lat_scale)
    end
    return hypot(Float64(first_point[1]) - Float64(second_point[1]), Float64(first_point[2]) - Float64(second_point[2]))
end


function workbench_cached_segment_matches_endpoints(segment::Vector{Vector{Float64}}, from_coordinates, to_coordinates)
    (from_coordinates === nothing || to_coordinates === nothing) && return true
    length(segment) >= 2 || return false

    from_distance = workbench_point_distance_meters(segment[1], from_coordinates)
    to_distance = workbench_point_distance_meters(segment[end], to_coordinates)
    return from_distance <= WORKBENCH_CACHE_ENDPOINT_TOLERANCE_METERS && to_distance <= WORKBENCH_CACHE_ENDPOINT_TOLERANCE_METERS
end


function workbench_cached_segment_by_keys(
    metric_cache,
    forward_key::AbstractString,
    reverse_key::AbstractString,
    from_coordinates=nothing,
    to_coordinates=nothing,
)
    metric_cache isa AbstractDict || return nothing

    if haskey(metric_cache, forward_key)
        segment = [Float64.(collect(point)) for point in metric_cache[forward_key]]
        workbench_cached_segment_matches_endpoints(segment, from_coordinates, to_coordinates) && return segment
        return nothing
    end

    if haskey(metric_cache, reverse_key)
        reverse_segment = [Float64.(collect(point)) for point in metric_cache[reverse_key]]
        segment = reverse(reverse_segment)
        workbench_cached_segment_matches_endpoints(segment, from_coordinates, to_coordinates) && return segment
    end
    return nothing
end


function workbench_cached_node_segment(metric_cache, from_node::Int, to_node::Int, from_coordinates=nothing, to_coordinates=nothing)
    return workbench_cached_segment_by_keys(
        metric_cache,
        workbench_node_edge_cache_key(from_node, to_node),
        workbench_node_edge_cache_key(to_node, from_node),
        from_coordinates,
        to_coordinates,
    )
end


function workbench_cached_segment(metric_cache, from_vertex::Int, to_vertex::Int, from_coordinates=nothing, to_coordinates=nothing)
    return workbench_cached_segment_by_keys(
        metric_cache,
        "$(from_vertex)_$(to_vertex)",
        "$(to_vertex)_$(from_vertex)",
        from_coordinates,
        to_coordinates,
    )
end


function workbench_merge_segments(segments::Vector{Vector{Vector{Float64}}})
    merged = Vector{Vector{Float64}}()
    for (index, segment) in enumerate(segments)
        start_index = index == 1 ? 1 : 2
        for point in segment[start_index:end]
            push!(merged, point)
        end
    end
    return merged
end


function workbench_straight_segment(node_coordinates::Dict{Int,Vector{Float64}}, from_node::Int, to_node::Int)
    haskey(node_coordinates, from_node) || throw(ArgumentError("Unknown instance node id $(from_node) in route payload"))
    haskey(node_coordinates, to_node) || throw(ArgumentError("Unknown instance node id $(to_node) in route payload"))
    return [node_coordinates[from_node], node_coordinates[to_node]]
end


function workbench_route_coordinates(route::AbstractVector, meta, metric::AbstractString)
    node_coordinates = workbench_node_coordinates_map(meta)
    graph_vertex_ids = workbench_graph_vertex_id_map(meta)
    road_cache = site_api_payload_get(meta, "road_cache", nothing)
    metric_cache = road_cache === nothing ? nothing : site_api_payload_get(road_cache, String(metric), nothing)
    depot_node_id = Int(site_api_payload_get(meta, "depot_instance_node_id", 1))

    full_route = [depot_node_id; Int.(collect(route)); depot_node_id]
    length(full_route) >= 2 || throw(ArgumentError("Routes must include at least one customer stop"))

    segments = Vector{Vector{Vector{Float64}}}()
    render_mode = "straight_line"
    used_cache = false
    cache_miss_count = 0

    for index in 1:(length(full_route) - 1)
        from_node = full_route[index]
        to_node = full_route[index + 1]
        segment = nothing
        if metric_cache isa AbstractDict
            segment = workbench_cached_node_segment(metric_cache, from_node, to_node, node_coordinates[from_node], node_coordinates[to_node])
            if segment === nothing && haskey(graph_vertex_ids, from_node) && haskey(graph_vertex_ids, to_node)
                segment = workbench_cached_segment(metric_cache, graph_vertex_ids[from_node], graph_vertex_ids[to_node], node_coordinates[from_node], node_coordinates[to_node])
            end
        end

        if segment === nothing
            cache_miss_count += 1
            segment = workbench_straight_segment(node_coordinates, from_node, to_node)
        else
            used_cache = true
        end
        push!(segments, segment)
    end

    if used_cache
        render_mode = cache_miss_count == 0 ? "cached_road" : "mixed"
    end

    return workbench_merge_segments(segments), render_mode, cache_miss_count
end


function workbench_render_routes_payload(payload; repo_root::AbstractString=default_site_repo_root())
    metric = String(site_api_payload_get(payload, "metric", "shortest"))
    metric in ("shortest", "fastest", "euclidean") || throw(ArgumentError("Unsupported metric '$(metric)'"))

    routes = workbench_parse_routes(payload)
    meta_path = site_api_payload_get(payload, "meta_path", nothing)
    if meta_path !== nothing && metric in ("shortest", "fastest")
        return workbench_render_routes_from_meta_path(repo_root, String(meta_path), routes, metric)
    end

    meta = site_api_payload_get(payload, "meta", nothing)
    meta === nothing && throw(ArgumentError("Missing required 'meta' object"))

    if metric in ("shortest", "fastest")
        return workbench_render_routes_with_live_routing(
            repo_root,
            meta,
            routes,
            metric;
            meta_file_path="",
            persist_cache=false,
        )
    end

    features = Any[]
    used_cache = false
    cache_miss_count = 0
    render_modes = Set{String}()

    for (route_index, route) in enumerate(routes)
        coordinates, render_mode, route_cache_misses = workbench_route_coordinates(route, meta, metric)
        render_mode == "cached_road" && (used_cache = true)
        render_mode == "mixed" && (used_cache = true)
        cache_miss_count += route_cache_misses
        push!(render_modes, render_mode)

        push!(features, Dict(
            "type" => "Feature",
            "geometry" => Dict(
                "type" => "LineString",
                "coordinates" => coordinates,
            ),
            "properties" => Dict(
                "route_index" => route_index,
                "stops" => length(route),
                "load" => workbench_route_demand(route, meta),
                "metric" => metric,
                "render_mode" => render_mode,
            ),
        ))
    end

    render_mode = if "mixed" in render_modes
        "mixed"
    elseif "cached_road" in render_modes
        "cached_road"
    else
        "straight_line"
    end

    return Dict(
        "ok" => true,
        "geojson" => Dict(
            "type" => "FeatureCollection",
            "features" => features,
        ),
        "summary" => Dict(
            "metric" => metric,
            "route_count" => length(routes),
            "render_mode" => render_mode,
            "used_cache" => used_cache,
            "cache_miss_count" => cache_miss_count,
            "straight_fallback_count" => cache_miss_count,
        ),
    )
end


function default_workbench_sample_root(repo_root::AbstractString=default_site_repo_root())
    return normpath(joinpath(canonical_site_repo_root(repo_root), "instances_v2", "osm"))
end


function default_workbench_osmdata_root(repo_root::AbstractString=default_site_repo_root())
    return normpath(joinpath(canonical_site_repo_root(repo_root), "osmdata"))
end


function workbench_local_osmdata_label(repo_root::AbstractString, osmdata_root::AbstractString)
    resolved_repo_root = canonical_site_repo_root(repo_root)
    resolved_osmdata_root = normpath(abspath(String(osmdata_root)))
    repo_root_with_sep = resolved_repo_root * Base.Filesystem.path_separator
    if resolved_osmdata_root == resolved_repo_root || startswith(resolved_osmdata_root, repo_root_with_sep)
        return relpath(resolved_osmdata_root, resolved_repo_root)
    end
    return resolved_osmdata_root
end


function workbench_preview_available(repo_root::AbstractString=default_site_repo_root())
    osmdata_root = default_workbench_osmdata_root(repo_root)
    return !isempty(workbench_osm_city_files(osmdata_root))
end


function workbench_city_label(slug::AbstractString)
    return titlecase(replace(String(slug), '-' => ' ', '_' => ' '))
end


function workbench_osm_city_slug(value::AbstractString)
    base = splitext(basename(String(value)))[1]
    normalized = lowercase(strip(base))
    normalized = replace(normalized, r"[^a-z0-9]+" => "_")
    normalized = replace(normalized, r"_+" => "_")
    normalized = strip(normalized, '_')
    return isempty(normalized) ? "x" : normalized
end


function workbench_osm_city_files(osmdata_root::AbstractString)
    isdir(osmdata_root) || return String[]
    files = String[]
    for entry in readdir(osmdata_root; join=true)
        isfile(entry) || continue
        endswith(lowercase(basename(entry)), ".osm") || continue
        push!(files, entry)
    end
    return sort(files; by=path -> workbench_osm_city_slug(path))
end


function workbench_sample_customer_counts(sample_root::AbstractString)
    counts_by_city = Dict{String,Vector{Int}}()
    isdir(sample_root) || return counts_by_city

    for city_dir in sort(filter(isdir, readdir(sample_root; join=true)); by=basename)
        counts = Int[]
        for size_dir in sort(filter(isdir, readdir(city_dir; join=true)); by=basename)
            count = workbench_size_dir_customer_count(size_dir)
            count === nothing || push!(counts, count)
        end
        unique!(counts)
        sort!(counts)
        counts_by_city[workbench_osm_city_slug(basename(city_dir))] = counts
    end
    return counts_by_city
end


function parse_workbench_size_dir_customer_count(size_dir_name::AbstractString)
    match_obj = match(r"^n(\d+)$", String(size_dir_name))
    match_obj === nothing && return nothing
    return max(parse(Int, match_obj.captures[1]) - 1, 0)
end


function workbench_manifest_files(size_dir::AbstractString)
    isdir(size_dir) || return String[]
    return sort(filter(path -> endswith(lowercase(path), "_manifest.json"), readdir(size_dir; join=true)))
end


function workbench_size_dir_customer_count(size_dir::AbstractString)
    for manifest_path in workbench_manifest_files(size_dir)
        manifest_payload = load_json_from_file(manifest_path)
        params = site_api_payload_get(manifest_payload, "params", nothing)
        n_customers = params === nothing ? nothing : site_api_payload_get(params, "n_customers", nothing)
        n_customers === nothing || return Int(n_customers)
    end
    return parse_workbench_size_dir_customer_count(basename(size_dir))
end


function workbench_generation_cities_payload(
    repo_root::AbstractString=default_site_repo_root();
    sample_root::AbstractString=default_workbench_sample_root(repo_root),
    osmdata_root::AbstractString=default_workbench_osmdata_root(repo_root),
)
    resolved_osmdata_root = normpath(abspath(String(osmdata_root)))
    sample_counts = workbench_sample_customer_counts(sample_root)
    cities = Any[]
    for osm_file in workbench_osm_city_files(resolved_osmdata_root)
        base_name = splitext(basename(osm_file))[1]
        slug = workbench_osm_city_slug(base_name)
        push!(cities, Dict(
            "slug" => slug,
            "label" => workbench_city_label(base_name),
            "customer_counts" => get(sample_counts, slug, Int[]),
            "osm_filename" => basename(osm_file),
            "osm_path" => workbench_to_repo_relative(repo_root, osm_file),
        ))
    end

    return Dict(
        "ok" => true,
        "preview_available" => !isempty(cities),
        "local_osmdata_dir" => workbench_local_osmdata_label(repo_root, resolved_osmdata_root),
        "cities" => cities,
    )
end


function workbench_node_coordinates(node)
    poi_lon = site_api_payload_get(node, "poi_lon", nothing)
    poi_lat = site_api_payload_get(node, "poi_lat", nothing)
    if poi_lon !== nothing && poi_lat !== nothing
        return [Float64(poi_lon), Float64(poi_lat)]
    end
    enu_x = site_api_payload_get(node, "enu_x", nothing)
    enu_y = site_api_payload_get(node, "enu_y", nothing)
    if enu_x !== nothing && enu_y !== nothing
        return [Float64(enu_x), Float64(enu_y)]
    end
    return nothing
end


function workbench_preview_geojson(meta_payload)
    nodes = site_api_payload_get(meta_payload, "nodes", nothing)
    nodes isa AbstractVector || throw(ArgumentError("Bundled preview meta.json is missing its nodes list"))

    depot_node_id = Int(site_api_payload_get(meta_payload, "depot_instance_node_id", 1))
    features = Any[]
    for node in nodes
        coordinates = workbench_node_coordinates(node)
        coordinates === nothing && continue
        instance_node_id_raw = site_api_payload_get(node, "instance_node_id", nothing)
        instance_node_id = instance_node_id_raw === nothing ? nothing : Int(instance_node_id_raw)
        role = instance_node_id == depot_node_id ? "depot" : "customer"
        push!(features, Dict(
            "type" => "Feature",
            "geometry" => Dict(
                "type" => "Point",
                "coordinates" => coordinates,
            ),
            "properties" => Dict(
                "role" => role,
                "source_tag" => "catalog_sample",
                "instance_node_id" => instance_node_id,
            ),
        ))
    end

    isempty(features) && throw(ArgumentError("Bundled preview meta.json did not yield any previewable nodes"))
    return Dict("type" => "FeatureCollection", "features" => features)
end


function select_workbench_sample_manifest(city_dir::AbstractString, requested_customers::Int, requested_method::AbstractString)
    size_dirs = sort(filter(isdir, readdir(city_dir; join=true)); by=path -> begin
        count = workbench_size_dir_customer_count(path)
        distance = count === nothing ? typemax(Int) : abs(count - requested_customers)
        return (distance, count === nothing ? typemax(Int) : count, basename(path))
    end)
    isempty(size_dirs) && throw(ArgumentError("No bundled sample sizes are available for city '$(basename(city_dir))'"))

    selected_size_dir = first(size_dirs)
    manifest_candidates = Any[]
    for manifest_path in workbench_manifest_files(selected_size_dir)
        manifest_payload = load_json_from_file(manifest_path)
        params = site_api_payload_get(manifest_payload, "params", nothing)
        sample_method = params === nothing ? nothing : site_api_payload_get(params, "method", nothing)
        push!(manifest_candidates, (path=manifest_path, payload=manifest_payload, method=sample_method))
    end
    isempty(manifest_candidates) && throw(ArgumentError("No bundled manifest files are available under '$(selected_size_dir)'"))

    sorted_candidates = sort(manifest_candidates; by=candidate -> ((candidate.method == requested_method) ? 0 : 1, basename(candidate.path)))
    selected_manifest = first(sorted_candidates)
    return selected_size_dir, selected_manifest.path, selected_manifest.payload
end


function workbench_generation_preview_payload(repo_root::AbstractString, payload; sample_root::AbstractString=default_workbench_sample_root(repo_root))
    city_slug = lowercase(strip(String(site_api_payload_get(payload, "city", ""))))
    isempty(city_slug) && throw(ArgumentError("Missing required preview field 'city'"))
    requested_method = String(site_api_payload_get(payload, "method", "poi_categories"))
    requested_customers_raw = site_api_payload_get(payload, "nCustomers", site_api_payload_get(payload, "n_customers", nothing))
    requested_customers_raw === nothing && throw(ArgumentError("Missing required preview field 'nCustomers'"))
    requested_customers = Int(requested_customers_raw)

    if !isdir(sample_root)
        return workbench_generation_full_preview_payload(payload; repo_root=repo_root)
    end

    city_dir = joinpath(sample_root, city_slug)
    if !isdir(city_dir)
        return workbench_generation_full_preview_payload(payload; repo_root=repo_root)
    end

    selected_size_dir, manifest_path, manifest_payload = select_workbench_sample_manifest(city_dir, requested_customers, requested_method)
    files_payload = site_api_payload_get(manifest_payload, "files", nothing)
    meta_filename = files_payload === nothing ? nothing : site_api_payload_get(files_payload, "meta", nothing)
    meta_filename === nothing && throw(ArgumentError("Bundled manifest '$(manifest_path)' does not reference a meta.json sidecar"))
    meta_payload = load_json_from_file(joinpath(dirname(manifest_path), String(meta_filename)))
    geojson = workbench_preview_geojson(meta_payload)

    params = site_api_payload_get(manifest_payload, "params", nothing)
    sample_method = params === nothing ? requested_method : String(site_api_payload_get(params, "method", requested_method))
    sample_city = params === nothing ? workbench_city_label(city_slug) : String(site_api_payload_get(params, "city", workbench_city_label(city_slug)))
    sample_customers = params === nothing ? requested_customers : Int(site_api_payload_get(params, "n_customers", requested_customers))
    customer_count = count(feature -> site_api_payload_get(site_api_payload_get(feature, "properties", Dict{String,Any}()), "role", "") == "customer", geojson["features"])
    note = ((sample_method == requested_method) && (sample_customers == requested_customers)) ?
        "Preview served from bundled sample metadata." :
        "Preview served from the closest bundled Mamut2026 sample because live OSM preview is unavailable."

    return Dict(
        "ok" => true,
        "geojson" => geojson,
        "summary" => Dict(
            "preview_mode" => "catalog_sample",
            "city" => sample_city,
            "method" => requested_method,
            "customers" => customer_count,
            "requested_customers" => requested_customers,
            "poi_customers" => customer_count,
            "parametric_customers" => 0,
            "sample_instance_name" => String(site_api_payload_get(manifest_payload, "base_name", basename(selected_size_dir))),
            "sample_method" => sample_method,
            "sample_size_dir" => basename(selected_size_dir),
            "note" => note,
        ),
    )
end


function workbench_parse_vrp_for_hgs(vrp_text::AbstractString)
    text = String(vrp_text)
    dim_match = match(r"DIMENSION\s*:\s*(\d+)"i, text)
    dim_match === nothing && throw(ArgumentError("Missing DIMENSION header in VRP text"))
    dimension = parse(Int, dim_match[1])

    cap_match = match(r"CAPACITY\s*:\s*(\d+)"i, text)
    cap_match === nothing && throw(ArgumentError("Missing CAPACITY header in VRP text"))
    capacity = parse(Int, cap_match[1])

    weight_match = match(r"EDGE_WEIGHT_SECTION\s*\n([\s\S]*?)\nNODE_COORD_SECTION"i, text)
    weight_match === nothing && throw(ArgumentError("Missing EDGE_WEIGHT_SECTION (HGS requires EXPLICIT FULL_MATRIX edge weights)"))
    weight_values = parse.(Float64, split(strip(weight_match[1])))
    expected_count = dimension * dimension
    length(weight_values) == expected_count || throw(ArgumentError(
        "EDGE_WEIGHT_SECTION has $(length(weight_values)) values, expected $(expected_count) for DIMENSION=$(dimension)"
    ))
    weights = Matrix(reshape(weight_values, (dimension, dimension))')

    demand_match = match(r"DEMAND_SECTION\s*\n([\s\S]*?)\nDEPOT_SECTION"i, text)
    demand_match === nothing && throw(ArgumentError("Missing DEMAND_SECTION in VRP text"))
    demands = zeros(Int, dimension)
    for line in split(strip(demand_match[1]), '\n')
        parts = split(strip(line))
        length(parts) >= 2 || continue
        index = parse(Int, parts[1])
        (1 <= index <= dimension) || throw(ArgumentError("DEMAND_SECTION references node $(index) outside [1, $(dimension)]"))
        demands[index] = parse(Int, parts[2])
    end

    return dimension, capacity, weights, demands
end


function workbench_extract_hgs_inputs_from_vrp_json(payload)
    payload isa AbstractDict || throw(ArgumentError("'vrp_json' must be an object"))

    capacity_raw = site_api_payload_get(payload, "vehicle_capacity", site_api_payload_get(payload, "capacity", nothing))
    capacity_raw === nothing && throw(ArgumentError("Instance JSON is missing 'vehicle_capacity'"))
    capacity = Int(capacity_raw)

    arc_costs = site_api_payload_get(payload, "arc_costs", nothing)
    arc_costs isa AbstractVector || throw(ArgumentError("Instance JSON is missing 'arc_costs' matrix"))
    dimension = length(arc_costs)
    dimension >= 2 || throw(ArgumentError("'arc_costs' must contain at least 2 rows"))

    weights = Matrix{Float64}(undef, dimension, dimension)
    for (row_index, row) in enumerate(arc_costs)
        row isa AbstractVector || throw(ArgumentError("'arc_costs' rows must be arrays"))
        length(row) == dimension || throw(ArgumentError("'arc_costs' must be square (row $(row_index) has length $(length(row)) for dimension $(dimension))"))
        for (col_index, value) in enumerate(row)
            weights[row_index, col_index] = Float64(value)
        end
    end

    demands_raw = site_api_payload_get(payload, "demands", nothing)
    demands_raw isa AbstractVector || throw(ArgumentError("Instance JSON is missing 'demands' array"))
    length(demands_raw) == dimension || throw(ArgumentError("'demands' length $(length(demands_raw)) must match dimension $(dimension)"))
    demands = [Int(value) for value in demands_raw]

    depot_raw = site_api_payload_get(payload, "depot", 0)
    depot_index = Int(depot_raw)
    depot_index == 0 || throw(ArgumentError("HGS solving currently requires depot index 0, got $(depot_index)"))

    return dimension, capacity, weights, demands
end


function workbench_solve_hgs_payload(payload)
    vrp_text = site_api_payload_get(payload, "vrp_text", nothing)
    vrp_json = site_api_payload_get(payload, "vrp_json", nothing)

    raw_time_limit = site_api_payload_get(payload, "time_limit", 30.0)
    time_limit = Float64(raw_time_limit)
    (isfinite(time_limit) && time_limit > 0.0) || throw(ArgumentError("'time_limit' must be a positive number"))

    local dimension::Int
    local capacity::Int
    local weights::Matrix{Float64}
    local demands::Vector{Int}
    local input_source::String
    if vrp_json !== nothing
        dimension, capacity, weights, demands = workbench_extract_hgs_inputs_from_vrp_json(vrp_json)
        input_source = "vrp_json"
    elseif vrp_text !== nothing
        vrp_text_string = String(vrp_text)
        isempty(strip(vrp_text_string)) && throw(ArgumentError("Empty 'vrp_text' field"))
        dimension, capacity, weights, demands = workbench_parse_vrp_for_hgs(vrp_text_string)
        input_source = "vrp_text"
    else
        throw(ArgumentError("Missing required 'vrp_text' or 'vrp_json' field"))
    end

    parameters = AlgorithmParameters(timeLimit=time_limit, seed=Int32(0))
    result = solve_cvrp(weights, demands, capacity, parameters; verbose=false)

    customer_routes = Vector{Vector{Int}}()
    for route in result.routes
        customers = Int[]
        for node_id in route
            id = Int(node_id)
            id == 1 && continue
            (2 <= id <= dimension) || throw(ArgumentError("HGS returned node $(id) outside [2, $(dimension)]"))
            push!(customers, id - 1)
        end
        isempty(customers) || push!(customer_routes, customers)
    end

    return Dict(
        "ok" => true,
        "cost" => result.cost,
        "time" => result.time,
        "routes" => customer_routes,
        "n_routes" => length(customer_routes),
        "dimension" => dimension,
        "capacity" => capacity,
        "input_source" => input_source,
    )
end


struct WorkbenchParsedCvrpInstance
    name::String
    comment::String
    dimension::Int
    capacity::Int
    arc_costs::Matrix{Int}
    coordinates::Vector{Tuple{Float64,Float64}}
    demands::Vector{Int}
    depot_node_index::Int
end


function workbench_parse_cvrp_vrp(filepath::AbstractString)
    headers = Dict{String,String}()
    edge_tokens = String[]
    coordinates = Tuple{Float64,Float64}[]
    demands_list = Int[]
    depot_indices = Int[]
    section = ""
    section_headers = Set([
        "EDGE_WEIGHT_SECTION", "NODE_COORD_SECTION", "DEMAND_SECTION", "DEPOT_SECTION", "EOF",
    ])

    for raw_line in eachline(filepath)
        line = strip(raw_line)
        isempty(line) && continue
        if line in section_headers
            section = line == "EOF" ? "" : line
            continue
        end
        if isempty(section)
            occursin(":", line) || continue
            key, value = strip.(split(line, ":"; limit=2))
            headers[String(key)] = String(value)
            continue
        end
        if section == "EDGE_WEIGHT_SECTION"
            append!(edge_tokens, split(line))
        elseif section == "NODE_COORD_SECTION"
            parts = split(line)
            length(parts) >= 3 || continue
            push!(coordinates, (parse(Float64, parts[2]), parse(Float64, parts[3])))
        elseif section == "DEMAND_SECTION"
            parts = split(line)
            length(parts) >= 2 || continue
            push!(demands_list, parse(Int, parts[2]))
        elseif section == "DEPOT_SECTION"
            line == "-1" && (section = ""; continue)
            push!(depot_indices, parse(Int, line))
        end
    end

    haskey(headers, "DIMENSION") || throw(ArgumentError("Missing DIMENSION header in $(filepath)"))
    haskey(headers, "CAPACITY") || throw(ArgumentError("Missing CAPACITY header in $(filepath)"))
    dimension = parse(Int, headers["DIMENSION"])
    capacity = parse(Int, headers["CAPACITY"])

    expected_count = dimension * dimension
    length(edge_tokens) == expected_count || throw(ArgumentError(
        "EDGE_WEIGHT_SECTION has $(length(edge_tokens)) tokens, expected $(expected_count) for DIMENSION=$(dimension) in $(filepath)"
    ))
    arc_costs = Matrix{Int}(undef, dimension, dimension)
    for row in 1:dimension
        offset = (row - 1) * dimension
        for col in 1:dimension
            arc_costs[row, col] = parse(Int, edge_tokens[offset + col])
        end
    end

    length(coordinates) == dimension || throw(ArgumentError(
        "NODE_COORD_SECTION has $(length(coordinates)) rows, expected $(dimension) in $(filepath)"
    ))
    length(demands_list) == dimension || throw(ArgumentError(
        "DEMAND_SECTION has $(length(demands_list)) rows, expected $(dimension) in $(filepath)"
    ))

    return WorkbenchParsedCvrpInstance(
        get(headers, "NAME", ""),
        get(headers, "COMMENT", ""),
        dimension,
        capacity,
        arc_costs,
        coordinates,
        demands_list,
        isempty(depot_indices) ? 1 : depot_indices[1],
    )
end


function workbench_resolve_osm_path(repo_root::AbstractString, city::AbstractString)
    isempty(city) && return ""
    osmdata_root = default_workbench_osmdata_root(repo_root)
    isdir(osmdata_root) || return ""
    target_slug = workbench_osm_city_slug(city)
    for entry in workbench_osm_city_files(osmdata_root)
        workbench_osm_city_slug(entry) == target_slug && return entry
    end
    return ""
end


function workbench_resolved_osm_city_name(repo_root::AbstractString, city::AbstractString)
    resolved = workbench_resolve_osm_path(repo_root, city)
    isempty(resolved) && return String(city)
    return splitext(basename(resolved))[1]
end


function workbench_ensure_local_osm_for_city!(repo_root::AbstractString, city::AbstractString)
    existing_path = workbench_resolve_osm_path(repo_root, city)
    !isempty(existing_path) && return existing_path

    local_osmdata_root = default_workbench_osmdata_root(repo_root)
    mkpath(local_osmdata_root)
    throw(ArgumentError("No OSM data for city '$(city)' was found in local osmdata folder '$(local_osmdata_root)'"))
end


function workbench_normalize_bulk_instances(raw_instances, repo_root::AbstractString)
    raw_instances isa AbstractVector || return raw_instances

    normalized_instances = Any[]
    for raw in raw_instances
        instance = Dict{Symbol,Any}()
        for (key, value) in pairs(raw)
            instance[Symbol(key)] = value
        end

        city_value = get(instance, :city, "")
        if city_value isa AbstractString && !isempty(strip(String(city_value)))
            resolved_path = workbench_resolve_osm_path(repo_root, city_value)
            if !isempty(resolved_path)
                instance[:city] = splitext(basename(resolved_path))[1]
                instance[:osmPath] = resolved_path
            end
        end
        push!(normalized_instances, instance)
    end
    return normalized_instances
end


function workbench_normalize_generation_payload(payload, repo_root::AbstractString)
    mutable = Dict{Symbol,Any}()
    for (key, value) in pairs(payload)
        mutable[Symbol(key)] = value
    end

    if haskey(mutable, :instances)
        mutable[:instances] = workbench_normalize_bulk_instances(mutable[:instances], repo_root)
    end

    if haskey(mutable, :cities)
        cities_value = mutable[:cities]
        if cities_value isa AbstractVector
            mutable[:cities] = [workbench_resolved_osm_city_name(repo_root, String(city)) for city in cities_value]
        elseif cities_value isa AbstractString
            mutable[:cities] = join(
                [workbench_resolved_osm_city_name(repo_root, strip(city)) for city in split(String(cities_value), ',') if !isempty(strip(city))],
                ",",
            )
        end
    end

    osm_path_value = get(mutable, :osmPath, "")
    if !(osm_path_value isa AbstractString) || isempty(strip(String(osm_path_value)))
        city = String(get(mutable, :city, ""))
        resolved = workbench_resolve_osm_path(repo_root, city)
        if !isempty(resolved)
            mutable[:osmPath] = resolved
            mutable[:city] = splitext(basename(resolved))[1]
        end
    end

    output_root_value = get(mutable, :outputRoot, "")
    if !(output_root_value isa AbstractString) || isempty(strip(String(output_root_value)))
        mutable[:outputRoot] = joinpath(canonical_site_repo_root(repo_root), "instances_v2")
    elseif !isabspath(String(output_root_value))
        mutable[:outputRoot] = joinpath(canonical_site_repo_root(repo_root), String(output_root_value))
    end

    return JSON3.read(JSON3.write(mutable))
end


function workbench_extract_reference_lla(meta_payload)
    ref = site_api_payload_get(meta_payload, "reference_lla", nothing)
    if ref isa AbstractDict
        return Dict(
            "lat" => Float64(site_api_payload_get(ref, "lat", 0.0)),
            "lon" => Float64(site_api_payload_get(ref, "lon", 0.0)),
            "alt" => Float64(site_api_payload_get(ref, "alt", 0.0)),
        )
    end
    return nothing
end


function workbench_to_repo_relative(repo_root::AbstractString, absolute_path::AbstractString)
    repo_root_resolved = rstrip(canonical_site_repo_root(repo_root), '/')
    absolute_resolved = rstrip(normpath(abspath(String(absolute_path))), '/')
    if absolute_resolved == repo_root_resolved || startswith(absolute_resolved, repo_root_resolved * "/")
        rel = relpath(absolute_resolved, repo_root_resolved)
        return startswith(rel, "..") ? absolute_resolved : rel
    end
    return absolute_resolved
end


function workbench_build_vrp_json_payload(
    parsed::WorkbenchParsedCvrpInstance,
    instance_name::AbstractString,
    metric_variant::AbstractString,
    place_slug::AbstractString,
    source_base_name::AbstractString,
    source_city::AbstractString,
    source_seed::Integer,
    source_folder::AbstractString,
    num_vehicles_lb::Union{Nothing,Integer},
    artifact_paths::AbstractDict,
    sibling_variant_paths::AbstractDict,
    reference_lla::Union{Nothing,AbstractDict},
    generated_at::AbstractString,
)
    coordinates_payload = [Float64[Float64(p[1]), Float64(p[2])] for p in parsed.coordinates]
    arc_costs_payload = [Int[parsed.arc_costs[row, col] for col in 1:size(parsed.arc_costs, 2)] for row in 1:size(parsed.arc_costs, 1)]

    metadata = Dict{String,Any}(
        "authors" => "OSM CVRP Workbench",
        "generated_at" => String(generated_at),
        "problem_type" => "CVRP",
        "metric_variant" => String(metric_variant),
        "place_slug" => String(place_slug),
        "source_base_name" => String(source_base_name),
        "source_city" => String(source_city),
        "source_seed" => Int(source_seed),
        "source_folder" => String(source_folder),
        "generator_version" => "mamut-routing-lib.workbench-v1",
        "artifact_paths" => artifact_paths,
        "sibling_variant_paths" => sibling_variant_paths,
        "derived_problem_paths" => Dict{String,String}(),
        "source_problem_paths" => Dict{String,String}(),
    )
    if num_vehicles_lb !== nothing
        metadata["num_vehicles_lb"] = Int(num_vehicles_lb)
    end

    payload = Dict{String,Any}(
        "instance_name" => String(instance_name),
        "instance_origin" => "OsmCvrpGen",
        "benchmark_name" => "Mamut2026",
        "num_customers" => parsed.dimension - 1,
        "vehicle_capacity" => parsed.capacity,
        "coordinates" => coordinates_payload,
        "demands" => parsed.demands,
        "depot" => parsed.depot_node_index - 1,
        "arc_costs" => arc_costs_payload,
        "metadata" => metadata,
    )
    if reference_lla !== nothing
        payload["reference_lla"] = reference_lla
    end
    return payload
end


function workbench_generation_full_preview_payload(payload; repo_root::AbstractString=default_site_repo_root())
    isdefined(@__MODULE__, :build_generation_selection) || throw(ArgumentError(
        "MAMUT OSM generation helpers are not available; ensure webapp/osm_generation.jl is present"
    ))

    normalized = workbench_normalize_generation_payload(payload, repo_root)
    sel = build_generation_selection(normalized)
    geo = preview_geojson(sel)
    source_tags = sel["source_tags"]
    poi_count = count(t -> t == "poi", source_tags[2:end])
    param_count = length(source_tags) - 1 - poi_count

    return Dict(
        "ok" => true,
        "geojson" => geo,
        "summary" => Dict(
            "preview_mode" => "osm",
            "city" => sel["params"]["city"],
            "method" => sel["params"]["method"],
            "customers" => Int(sel["params"]["n_customers"]),
            "poi_customers" => poi_count,
            "parametric_customers" => param_count,
        ),
    )
end


function workbench_generation_fetch_osm_city_payload(payload; repo_root::AbstractString=default_site_repo_root())
    isdefined(@__MODULE__, :fetch_and_store_city_osm) || throw(ArgumentError(
        "MAMUT OSM fetch helpers are not available; ensure webapp/osm_generation.jl is present"
    ))

    mutable = Dict{Symbol,Any}()
    for (key, value) in pairs(payload)
        mutable[Symbol(key)] = value
    end

    osm_dir_value = get(mutable, :osmDir, "")
    osmdata_root = if !(osm_dir_value isa AbstractString) || isempty(strip(String(osm_dir_value)))
        default_workbench_osmdata_root(repo_root)
    elseif isabspath(String(osm_dir_value))
        normpath(String(osm_dir_value))
    else
        normpath(joinpath(canonical_site_repo_root(repo_root), String(osm_dir_value)))
    end
    mkpath(osmdata_root)
    mutable[:osmDir] = osmdata_root

    result = fetch_and_store_city_osm(mutable)
    result["local_osmdata_dir"] = workbench_local_osmdata_label(repo_root, osmdata_root)
    result["cities"] = [entry["slug"] for entry in workbench_generation_cities_payload(repo_root; osmdata_root=osmdata_root)["cities"]]
    return result
end


const VRPTW_HORIZON_START = 0
const VRPTW_HORIZON_END = 86400
const VRPTW_EUCLIDEAN_SPEED_MPS = 14
const VRPTW_PROBLEM_TYPES = ("CVRP", "VRPTW")
const VRPTW_TW_METHODS = ("route_centered", "reachable_interval")
const VRPTW_DEFAULT_TW_METHOD = "route_centered"


function workbench_clamp_float(value::Real, lo::Real, hi::Real)
    return value < lo ? lo : (value > hi ? hi : value)
end


function workbench_convert_meters_to_seconds(matrix::AbstractMatrix; speed_mps::Real=VRPTW_EUCLIDEAN_SPEED_MPS)
    rows = size(matrix, 1)
    cols = size(matrix, 2)
    converted = Matrix{Int}(undef, rows, cols)
    speed = Float64(speed_mps)
    for r in 1:rows, c in 1:cols
        converted[r, c] = ceil(Int, Float64(matrix[r, c]) / speed)
    end
    return converted
end


function workbench_nearest_neighbour_route(travel_times::AbstractMatrix; depot::Int=1)
    n = size(travel_times, 1)
    n >= 1 || throw(ArgumentError("Travel-time matrix is empty"))
    visited = falses(n)
    visited[depot] = true
    route = Int[depot]
    current = depot
    while length(route) < n
        best = 0
        best_cost = typemax(Int)
        for j in 1:n
            visited[j] && continue
            j == current && continue
            cost = Int(travel_times[current, j])
            if cost < best_cost
                best_cost = cost
                best = j
            end
        end
        best == 0 && break
        push!(route, best)
        visited[best] = true
        current = best
    end
    return route
end


function workbench_simulate_arrival_times(
    route::AbstractVector{<:Integer},
    travel_times::AbstractMatrix,
    service_times::AbstractVector{<:Integer};
    horizon_start::Integer=VRPTW_HORIZON_START,
)
    n = size(travel_times, 1)
    arrivals = fill(Int(horizon_start), n)
    isempty(route) && return arrivals
    t = Int(horizon_start)
    indices = collect(eachindex(route))
    prev = Int(route[first(indices)])
    arrivals[prev] = t
    for k in indices[2:end]
        cur = Int(route[k])
        t += Int(travel_times[prev, cur])
        arrivals[cur] = t
        t += Int(service_times[cur])
        prev = cur
    end
    return arrivals
end


function workbench_repair_time_window(
    tw_start::Integer,
    tw_end::Integer,
    travel_to::Integer,
    travel_back::Integer,
    service::Integer,
    horizon_start::Integer,
    horizon_end::Integer,
)
    earliest_feasible = Int(horizon_start) + Int(travel_to)
    latest_feasible = Int(horizon_end) - Int(service) - Int(travel_back)

    if latest_feasible < earliest_feasible
        clamped = clamp(div(earliest_feasible + latest_feasible, 2), Int(horizon_start), Int(horizon_end))
        return clamped, clamped
    end

    e = max(Int(tw_start), earliest_feasible)
    l = min(Int(tw_end), latest_feasible)
    if e > l
        e = earliest_feasible
        l = latest_feasible
    end
    return e, l
end


function workbench_generate_service_times(
    rng::AbstractRNG,
    n_total::Integer,
    horizon_start::Integer,
    horizon_end::Integer;
    mean_ratio_target::Float64=0.01,
    mean_ratio_std::Float64=0.005,
    depot::Integer=1,
)
    horizon = Float64(horizon_end - horizon_start)
    mean_ratio = workbench_clamp_float(randn(rng) * mean_ratio_std + mean_ratio_target, 0.001, 0.2)
    mean_service = horizon * mean_ratio
    upper = max(1, Int(floor(mean_service * 2)))
    service_times = zeros(Int, Int(n_total))
    for i in 1:Int(n_total)
        i == Int(depot) && continue
        sampled = randn(rng) * (mean_service / 2.0) + mean_service
        service_times[i] = clamp(round(Int, sampled), 1, upper)
    end
    return service_times, mean_ratio
end


function workbench_generate_tw_route_centered(
    rng::AbstractRNG,
    travel_times::AbstractMatrix,
    service_times::AbstractVector{<:Integer},
    horizon_start::Integer,
    horizon_end::Integer;
    depot::Integer=1,
    width_ratio_mean::Float64=0.2,
    width_ratio_std::Float64=0.08,
)
    n = size(travel_times, 1)
    horizon = Float64(horizon_end - horizon_start)
    route = workbench_nearest_neighbour_route(travel_times; depot=Int(depot))
    arrivals = workbench_simulate_arrival_times(route, travel_times, service_times; horizon_start=horizon_start)

    time_windows = Vector{Tuple{Int,Int}}(undef, n)
    time_windows[Int(depot)] = (Int(horizon_start), Int(horizon_end))
    for i in 1:n
        i == Int(depot) && continue
        center = arrivals[i]
        width_ratio = workbench_clamp_float(randn(rng) * width_ratio_std + width_ratio_mean, 0.01, 1.0)
        width = max(1, round(Int, horizon * width_ratio))
        e = round(Int, center - width / 2)
        l = round(Int, center + width / 2)
        e, l = workbench_repair_time_window(
            e, l,
            Int(travel_times[Int(depot), i]),
            Int(travel_times[i, Int(depot)]),
            Int(service_times[i]),
            Int(horizon_start), Int(horizon_end),
        )
        time_windows[i] = (e, l)
    end
    return time_windows, route, width_ratio_mean
end


function workbench_generate_tw_reachable_interval(
    rng::AbstractRNG,
    travel_times::AbstractMatrix,
    service_times::AbstractVector{<:Integer},
    horizon_start::Integer,
    horizon_end::Integer;
    depot::Integer=1,
    width_ratio_mean::Float64=0.5,
    width_ratio_std::Float64=0.2,
)
    n = size(travel_times, 1)
    horizon = Float64(horizon_end - horizon_start)
    time_windows = Vector{Tuple{Int,Int}}(undef, n)
    time_windows[Int(depot)] = (Int(horizon_start), Int(horizon_end))
    for i in 1:n
        i == Int(depot) && continue
        travel_to = Int(travel_times[Int(depot), i])
        travel_back = Int(travel_times[i, Int(depot)])
        service_i = Int(service_times[i])
        earliest = Int(horizon_start) + travel_to
        latest = Int(horizon_end) - service_i - travel_back

        width_ratio = workbench_clamp_float(randn(rng) * width_ratio_std + width_ratio_mean, 0.01, 1.0)
        width = max(1, round(Int, horizon * width_ratio))

        if latest < earliest
            clamped = clamp(earliest, Int(horizon_start), Int(horizon_end))
            time_windows[i] = (clamped, clamped)
            continue
        end

        center_low = earliest + div(width, 2)
        center_high = latest - div(width, 2)
        center = if center_low > center_high
            div(earliest + latest, 2)
        else
            rand(rng, center_low:center_high)
        end
        e = center - div(width, 2)
        l = e + width
        e, l = workbench_repair_time_window(
            e, l, travel_to, travel_back, service_i, Int(horizon_start), Int(horizon_end),
        )
        time_windows[i] = (e, l)
    end
    return time_windows, width_ratio_mean
end


function workbench_generate_vrptw_fields(
    seed_parts::Tuple,
    travel_times::AbstractMatrix,
    horizon_start::Integer,
    horizon_end::Integer,
    tw_method::AbstractString;
    depot::Integer=1,
)
    seed_value = Int(abs(hash(seed_parts) % UInt(typemax(Int64))))
    rng = MersenneTwister(seed_value)
    n = size(travel_times, 1)
    service_times, mean_service_ratio = workbench_generate_service_times(
        rng, n, horizon_start, horizon_end; depot=depot,
    )

    tw_method_lower = lowercase(strip(String(tw_method)))
    tw_method_lower in VRPTW_TW_METHODS || throw(ArgumentError(
        "Unsupported TW method '$(tw_method)'. Use one of: $(join(VRPTW_TW_METHODS, ", "))."
    ))

    if tw_method_lower == "route_centered"
        result_tuple = workbench_generate_tw_route_centered(
            rng, travel_times, service_times, horizon_start, horizon_end; depot=depot,
        )
        time_windows = result_tuple[1]
        width_ratio_mean = result_tuple[3]
    else
        time_windows, width_ratio_mean = workbench_generate_tw_reachable_interval(
            rng, travel_times, service_times, horizon_start, horizon_end; depot=depot,
        )
    end

    repaired_count = 0
    for i in 1:n
        i == Int(depot) && continue
        e_in, l_in = time_windows[i]
        e_out, l_out = workbench_repair_time_window(
            e_in, l_in,
            Int(travel_times[Int(depot), i]),
            Int(travel_times[i, Int(depot)]),
            Int(service_times[i]),
            Int(horizon_start), Int(horizon_end),
        )
        (e_out == e_in && l_out == l_in) || (repaired_count += 1)
        time_windows[i] = (e_out, l_out)
    end

    stochastic_params = Dict{String,Any}(
        "tw_method" => tw_method_lower,
        "horizon_start" => Int(horizon_start),
        "horizon_end" => Int(horizon_end),
        "mean_service_time_horizon_ratio" => mean_service_ratio,
        "time_window_ratio" => width_ratio_mean,
        "tw_repaired_count" => repaired_count,
    )
    return service_times, time_windows, stochastic_params
end


function workbench_write_cvrptw_vrp(
    filepath::AbstractString,
    parsed::WorkbenchParsedCvrpInstance,
    instance_name::AbstractString,
    comment::AbstractString,
    service_times::AbstractVector{<:Integer},
    time_windows::AbstractVector{<:Tuple{<:Integer,<:Integer}},
)
    mkpath(dirname(filepath))
    open(filepath, "w") do io
        println(io, "NAME : $(instance_name)")
        println(io, "TYPE : CVRPTW")
        isempty(comment) || println(io, "COMMENT : $(comment)")
        println(io, "DIMENSION : $(parsed.dimension)")
        println(io, "CAPACITY : $(parsed.capacity)")
        println(io, "EDGE_WEIGHT_TYPE : EXPLICIT")
        println(io, "EDGE_WEIGHT_FORMAT : FULL_MATRIX")
        println(io, "EDGE_WEIGHT_SECTION")
        for row in 1:size(parsed.arc_costs, 1)
            println(io, join((parsed.arc_costs[row, col] for col in 1:size(parsed.arc_costs, 2)), ' '))
        end
        println(io, "NODE_COORD_SECTION")
        for (index, (x, y)) in enumerate(parsed.coordinates)
            println(io, index, " ", x, " ", y)
        end
        println(io, "DEMAND_SECTION")
        for (index, demand) in enumerate(parsed.demands)
            println(io, index, " ", demand)
        end
        println(io, "TIME_WINDOW_SECTION")
        for (index, (ready, due)) in enumerate(time_windows)
            println(io, index, " ", ready, " ", due)
        end
        println(io, "SERVICE_TIME_SECTION")
        for (index, service) in enumerate(service_times)
            println(io, index, " ", service)
        end
        println(io, "DEPOT_SECTION")
        println(io, parsed.depot_node_index)
        println(io, -1)
        println(io, "EOF")
    end
    return nothing
end


function workbench_build_vrptw_json_payload(
    parsed::WorkbenchParsedCvrpInstance,
    instance_name::AbstractString,
    metric_variant::AbstractString,
    place_slug::AbstractString,
    source_base_name::AbstractString,
    source_city::AbstractString,
    source_seed::Integer,
    source_folder::AbstractString,
    num_vehicles_lb::Union{Nothing,Integer},
    artifact_paths::AbstractDict,
    sibling_variant_paths::AbstractDict,
    source_problem_paths::AbstractDict,
    reference_lla::Union{Nothing,AbstractDict},
    service_times::AbstractVector{<:Integer},
    time_windows::AbstractVector{<:Tuple{<:Integer,<:Integer}},
    stochastic_params::AbstractDict,
    generated_at::AbstractString,
)
    payload = workbench_build_vrp_json_payload(
        parsed, instance_name, metric_variant, place_slug, source_base_name, source_city,
        source_seed, source_folder, num_vehicles_lb, artifact_paths, sibling_variant_paths,
        reference_lla, generated_at,
    )
    payload["service_times"] = [Int(value) for value in service_times]
    payload["time_windows"] = [Int[Int(tw[1]), Int(tw[2])] for tw in time_windows]
    metadata = payload["metadata"]
    metadata["problem_type"] = "VRPTW"
    metadata["source_problem_paths"] = source_problem_paths
    metadata["vrptw_derivation"] = stochastic_params
    return payload
end


function workbench_postprocess_vrptw_instance(
    repo_root::AbstractString,
    cvrp_folder::AbstractString,
    cvrp_base::AbstractString,
    cvrp_metric_to_filename::AbstractDict,
    cvrp_meta_filename::AbstractString,
    cvrp_manifest_filename::AbstractString,
    cvrp_summary,
    cvrp_reference_lla,
    place_slug::AbstractString,
    source_seed::Integer,
    cvrp_folder_relative::AbstractString,
    cvrp_vrp_json_paths_relative::AbstractDict,
    tw_method::AbstractString,
    horizon_start::Integer,
    horizon_end::Integer,
)
    fastest_filename = String(get(cvrp_metric_to_filename, "fastest", ""))
    isempty(fastest_filename) && throw(ArgumentError("CVRP fastest .vrp filename missing for VRPTW derivation"))

    metric_order = ("fastest",)
    metric_to_filename = Dict{String,String}()
    original_parsed_by_metric = Dict{String,WorkbenchParsedCvrpInstance}()
    for metric in metric_order
        filename = String(get(cvrp_metric_to_filename, metric, ""))
        isempty(filename) && continue
        vrp_path = joinpath(cvrp_folder, filename)
        isfile(vrp_path) || throw(ArgumentError("CVRP $(metric) .vrp not found at $(vrp_path)"))
        metric_to_filename[metric] = filename
        original_parsed_by_metric[metric] = workbench_parse_cvrp_vrp(vrp_path)
    end

    fastest_parsed = original_parsed_by_metric["fastest"]
    travel_times_fastest = copy(fastest_parsed.arc_costs)

    seed_parts = (cvrp_base, place_slug, source_seed, tw_method, horizon_start, horizon_end, "vrptw_workbench_v1")
    service_times, time_windows, stochastic_params = workbench_generate_vrptw_fields(
        seed_parts, travel_times_fastest, horizon_start, horizon_end, tw_method;
        depot=fastest_parsed.depot_node_index,
    )

    vrptw_id = String(cvrp_base)

    route_count_value = (cvrp_summary isa AbstractDict && haskey(cvrp_summary, "route_count")) ?
        Int(site_api_payload_get(cvrp_summary, "route_count", 0)) : nothing
    generated_at = string(now())

    metric_to_vrp_json_filename = Dict(
        metric => replace(filename, r"\.vrp$" => ".vrp.json")
        for (metric, filename) in metric_to_filename
    )
    files = Dict{String,Any}()
    for metric in metric_order
        haskey(metric_to_filename, metric) || continue
        original = original_parsed_by_metric[metric]
        metric_instance_id = "$(cvrp_base)_$(metric)"
        parsed = WorkbenchParsedCvrpInstance(
            metric_instance_id,
            original.comment,
            original.dimension,
            original.capacity,
            copy(original.arc_costs),
            original.coordinates,
            original.demands,
            original.depot_node_index,
        )

        vrp_filename = metric_to_filename[metric]
        vrp_json_filename = metric_to_vrp_json_filename[metric]
        vrp_relative = joinpath(cvrp_folder_relative, vrp_filename)
        vrp_json_relative = joinpath(cvrp_folder_relative, vrp_json_filename)
        artifact_paths = Dict{String,String}(
            "vrp_json" => vrp_json_relative,
            "vrp" => vrp_relative,
            "meta" => isempty(cvrp_meta_filename) ? "" : joinpath(cvrp_folder_relative, cvrp_meta_filename),
            "manifest" => joinpath(cvrp_folder_relative, cvrp_manifest_filename),
        )
        sibling_variant_paths = Dict{String,String}()
        for (other_metric, other_json_filename) in metric_to_vrp_json_filename
            other_metric == metric && continue
            sibling_variant_paths[other_metric] = joinpath(cvrp_folder_relative, other_json_filename)
        end

        workbench_write_cvrptw_vrp(
            joinpath(cvrp_folder, vrp_filename), parsed,
            metric_instance_id, parsed.comment, service_times, time_windows,
        )
        json_payload = workbench_build_vrptw_json_payload(
            parsed, metric_instance_id, metric, place_slug, cvrp_base, place_slug,
            source_seed, cvrp_folder_relative, route_count_value,
            artifact_paths, sibling_variant_paths,
            Dict{String,String}(
                "cvrp_vrp_json" => get(cvrp_vrp_json_paths_relative, metric, ""),
                "cvrp_vrp" => vrp_relative,
            ),
            cvrp_reference_lla, service_times, time_windows, stochastic_params, generated_at,
        )
        save_json_to_file(json_payload, joinpath(cvrp_folder, vrp_json_filename); indent=4, sort_keys=false)

        files["$(metric)_vrp"] = vrp_relative
        files["$(metric)_vrp_json"] = vrp_json_relative
    end
    if !isempty(cvrp_meta_filename)
        files["meta"] = joinpath(cvrp_folder_relative, cvrp_meta_filename)
    end
    files["manifest"] = joinpath(cvrp_folder_relative, cvrp_manifest_filename)

    cvrp_meta_path_abs = isempty(cvrp_meta_filename) ? "" : joinpath(cvrp_folder, cvrp_meta_filename)
    if !isempty(cvrp_meta_path_abs) && isfile(cvrp_meta_path_abs)
        meta_payload = load_json_from_file(cvrp_meta_path_abs)
        meta_payload_dict = if meta_payload isa AbstractDict
            Dict{String,Any}(String(k) => v for (k, v) in pairs(meta_payload))
        else
            Dict{String,Any}()
        end
        meta_payload_dict["instance_id"] = vrptw_id
        meta_payload_dict["problem_type"] = "VRPTW"
        meta_payload_dict["vrptw_derivation"] = stochastic_params
        save_json_to_file(meta_payload_dict, cvrp_meta_path_abs; indent=4, sort_keys=false)
    end

    cvrp_manifest_path_abs = isempty(cvrp_manifest_filename) ? "" : joinpath(cvrp_folder, cvrp_manifest_filename)
    if !isempty(cvrp_manifest_path_abs) && isfile(cvrp_manifest_path_abs)
        manifest_payload = load_json_from_file(cvrp_manifest_path_abs)
        manifest_dict = if manifest_payload isa AbstractDict
            Dict{String,Any}(String(k) => v for (k, v) in pairs(manifest_payload))
        else
            Dict{String,Any}()
        end
        manifest_dict["instance_id"] = vrptw_id
        manifest_dict["problem_type"] = "VRPTW"
        manifest_params_raw = get(manifest_dict, "params", Dict{String,Any}())
        manifest_params = manifest_params_raw isa AbstractDict ?
            Dict{String,Any}(String(k) => v for (k, v) in pairs(manifest_params_raw)) :
            Dict{String,Any}()
        manifest_params["vrptw_derivation"] = stochastic_params
        manifest_dict["params"] = manifest_params
        save_json_to_file(manifest_dict, cvrp_manifest_path_abs; indent=4, sort_keys=false)
    end

    return (
        vrptw_instance_id = vrptw_id,
        folder_relative = cvrp_folder_relative,
        folder_fastest_relative = cvrp_folder_relative,
        sidecar_relative = cvrp_folder_relative,
        files = files,
        service_times = service_times,
        time_windows = time_windows,
        stochastic_params = stochastic_params,
    )
end


function workbench_postprocess_generated_instance(
    repo_root::AbstractString,
    folder::AbstractString,
    base::AbstractString,
    files_payload,
    manifest_filename::AbstractString,
    summary_payload,
)
    metric_to_filename = Dict{String,String}()
    for metric in ("shortest", "fastest", "euclidean")
        value = nothing
        if files_payload isa AbstractDict
            value = haskey(files_payload, metric) ? files_payload[metric] : get(files_payload, Symbol(metric), nothing)
        end
        if value !== nothing
            metric_to_filename[metric] = String(value)
        end
    end

    meta_filename = ""
    if files_payload isa AbstractDict
        meta_filename = String(get(files_payload, "meta", get(files_payload, :meta, "")))
    end
    meta_path = isempty(meta_filename) ? "" : joinpath(folder, meta_filename)
    reference_lla_payload = nothing
    if !isempty(meta_path) && isfile(meta_path)
        try
            reference_lla_payload = workbench_extract_reference_lla(load_json_from_file(meta_path))
        catch error
            @warn "Failed to read reference_lla from generated meta" path=meta_path error=error
        end
    end

    manifest_path = joinpath(folder, manifest_filename)
    manifest_payload = isfile(manifest_path) ? load_json_from_file(manifest_path) : Dict{String,Any}()
    manifest_params = site_api_payload_get(manifest_payload, "params", Dict{String,Any}())
    place_slug = String(site_api_payload_get(manifest_params, "city", ""))
    source_seed = Int(site_api_payload_get(manifest_params, "seed", 0))
    route_count = (summary_payload isa AbstractDict && haskey(summary_payload, "route_count")) ?
        Int(site_api_payload_get(summary_payload, "route_count", 0)) : nothing

    folder_relative = workbench_to_repo_relative(repo_root, folder)
    generated_at = string(now())

    vrp_json_paths_relative = Dict{String,String}()
    vrp_json_filenames = Dict{String,String}()
    for (metric, vrp_filename) in metric_to_filename
        vrp_json_filenames[metric] = replace(vrp_filename, r"\.vrp$" => ".vrp.json")
    end

    for (metric, vrp_filename) in metric_to_filename
        vrp_path = joinpath(folder, vrp_filename)
        parsed = workbench_parse_cvrp_vrp(vrp_path)

        vrp_json_filename = vrp_json_filenames[metric]
        vrp_json_relative = joinpath(folder_relative, vrp_json_filename)

        artifact_paths = Dict{String,String}(
            "vrp_json" => vrp_json_relative,
            "vrp" => joinpath(folder_relative, vrp_filename),
            "meta" => isempty(meta_filename) ? "" : joinpath(folder_relative, meta_filename),
            "manifest" => joinpath(folder_relative, manifest_filename),
        )
        sibling_variant_paths = Dict{String,String}()
        for (other_metric, _) in metric_to_filename
            other_metric == metric && continue
            sibling_variant_paths[other_metric] = joinpath(folder_relative, vrp_json_filenames[other_metric])
        end

        instance_id = base * "_" * metric
        json_payload = workbench_build_vrp_json_payload(
            parsed,
            instance_id,
            metric,
            place_slug,
            base,
            place_slug,
            source_seed,
            folder_relative,
            route_count,
            artifact_paths,
            sibling_variant_paths,
            reference_lla_payload,
            generated_at,
        )

        vrp_json_disk_path = joinpath(folder, vrp_json_filename)
        save_json_to_file(json_payload, vrp_json_disk_path; indent=4, sort_keys=false)
        vrp_json_paths_relative[metric] = vrp_json_relative
    end

    return (
        folder=folder,
        folder_relative=folder_relative,
        metric_to_filename=metric_to_filename,
        meta_filename=meta_filename,
        manifest_filename=manifest_filename,
        vrp_json_paths=vrp_json_paths_relative,
        reference_lla=reference_lla_payload,
        place_slug=place_slug,
        source_seed=source_seed,
    )
end


function workbench_normalize_problem_type(value, default::AbstractString="CVRP")
    raw = String(value === nothing ? default : value)
    cleaned = uppercase(strip(raw))
    isempty(cleaned) && (cleaned = uppercase(default))
    cleaned in VRPTW_PROBLEM_TYPES || throw(ArgumentError(
        "Unsupported problemType '$(raw)'. Use one of: $(join(VRPTW_PROBLEM_TYPES, ", "))."
    ))
    return cleaned
end


function workbench_normalize_tw_method(value, default::AbstractString=VRPTW_DEFAULT_TW_METHOD)
    raw = String(value === nothing ? default : value)
    cleaned = lowercase(strip(raw))
    isempty(cleaned) && (cleaned = default)
    cleaned in VRPTW_TW_METHODS || throw(ArgumentError(
        "Unsupported twMethod '$(raw)'. Use one of: $(join(VRPTW_TW_METHODS, ", "))."
    ))
    return cleaned
end


function workbench_first_payload_value(payload, keys::Tuple, default=nothing)
    for key in keys
        value = site_api_payload_get(payload, String(key), nothing)
        value === nothing || return value
    end
    return default
end


function workbench_extract_horizon(payload, key::AbstractString, default::Integer)
    raw = site_api_payload_get(payload, key, nothing)
    return workbench_normalize_horizon_value(raw, default)
end


function workbench_normalize_horizon_value(raw, default::Integer)
    raw === nothing && return Int(default)
    if raw isa AbstractString
        stripped = strip(raw)
        isempty(stripped) && return Int(default)
        return parse(Int, stripped)
    end
    return Int(raw)
end


function workbench_collect_tw_options(payload)
    method_value = workbench_first_payload_value(payload, ("twMethod", "tw_method"), VRPTW_DEFAULT_TW_METHOD)
    horizon_start_value = workbench_first_payload_value(payload, ("twHorizonStart", "tw_horizon_start"), nothing)
    horizon_end_value = workbench_first_payload_value(payload, ("twHorizonEnd", "tw_horizon_end"), nothing)
    method = workbench_normalize_tw_method(method_value)
    horizon_start = workbench_normalize_horizon_value(horizon_start_value, VRPTW_HORIZON_START)
    horizon_end = workbench_normalize_horizon_value(horizon_end_value, VRPTW_HORIZON_END)
    horizon_end > horizon_start || throw(ArgumentError("twHorizonEnd must be greater than twHorizonStart"))
    return (tw_method=method, horizon_start=horizon_start, horizon_end=horizon_end)
end


function workbench_run_vrptw_post(
    repo_root::AbstractString,
    cvrp_artefact,
    cvrp_summary,
    tw_options;
)
    isempty(cvrp_artefact.metric_to_filename) && return nothing
    haskey(cvrp_artefact.metric_to_filename, "fastest") || return nothing

    vrptw = workbench_postprocess_vrptw_instance(
        repo_root,
        cvrp_artefact.folder,
        # base_name == cvrp_artefact.metric_to_filename "fastest" minus "_fastest.vrp"
        replace(String(cvrp_artefact.metric_to_filename["fastest"]), r"_fastest\.vrp$" => ""),
        cvrp_artefact.metric_to_filename,
        cvrp_artefact.meta_filename,
        cvrp_artefact.manifest_filename,
        cvrp_summary,
        cvrp_artefact.reference_lla,
        cvrp_artefact.place_slug,
        cvrp_artefact.source_seed,
        cvrp_artefact.folder_relative,
        cvrp_artefact.vrp_json_paths,
        tw_options.tw_method,
        tw_options.horizon_start,
        tw_options.horizon_end,
    )

    return Dict{String,Any}(
        "ok" => true,
        "instance_id" => vrptw.vrptw_instance_id,
        "folder_relative" => vrptw.folder_relative,
        "folder_fastest_relative" => vrptw.folder_fastest_relative,
        "sidecar_relative" => vrptw.sidecar_relative,
        "files" => vrptw.files,
        "stochastic_params" => vrptw.stochastic_params,
        "horizon_start" => tw_options.horizon_start,
        "horizon_end" => tw_options.horizon_end,
        "tw_method" => tw_options.tw_method,
    )
end


function workbench_generation_single_payload(payload; repo_root::AbstractString=default_site_repo_root())
    isdefined(@__MODULE__, :generate_single_instance) || throw(ArgumentError(
        "MAMUT OSM generation helpers are not available; ensure webapp/osm_generation.jl is present"
    ))

    problem_type = workbench_normalize_problem_type(workbench_first_payload_value(payload, ("problemType", "problem_type"), "CVRP"))
    tw_options = problem_type == "VRPTW" ? workbench_collect_tw_options(payload) : nothing

    normalized = workbench_normalize_generation_payload(payload, repo_root)
    raw_result = generate_single_instance(normalized)

    folder = String(raw_result["folder"])
    base = String(raw_result["base_name"])
    files_payload = raw_result["files"]
    summary_payload = raw_result["summary"]
    manifest_filename = String(raw_result["manifest"])

    artefact = workbench_postprocess_generated_instance(
        repo_root, folder, base, files_payload, manifest_filename, summary_payload,
    )

    response_files = Dict{String,Any}(
        "shortest" => get(artefact.metric_to_filename, "shortest", ""),
        "fastest" => get(artefact.metric_to_filename, "fastest", ""),
        "euclidean" => get(artefact.metric_to_filename, "euclidean", ""),
        "meta" => artefact.meta_filename,
        "manifest" => manifest_filename,
    )

    response = Dict{String,Any}(
        "ok" => true,
        "problem_type" => problem_type,
        "base_name" => base,
        "folder" => folder,
        "folder_relative" => artefact.folder_relative,
        "files" => response_files,
        "vrp_json_paths" => artefact.vrp_json_paths,
        "manifest" => manifest_filename,
        "summary" => summary_payload,
        "reference_lla" => artefact.reference_lla,
    )

    if tw_options !== nothing
        vrptw_summary = workbench_run_vrptw_post(repo_root, artefact, summary_payload, tw_options)
        vrptw_summary === nothing && throw(ArgumentError(
            "Cannot derive VRPTW: CVRP fastest variant is missing for $(base)"
        ))
        response["vrptw"] = vrptw_summary
    end

    return response
end


function workbench_bulk_tuning_value(instance, normalized_payload, key::AbstractString, default)
    value = site_api_payload_get(instance, key, nothing)
    value === nothing && return site_api_payload_get(normalized_payload, key, default)
    return value
end


function workbench_bulk_tuning_value_first(instance, normalized_payload, keys::Tuple, default)
    for key in keys
        value = site_api_payload_get(instance, String(key), nothing)
        value === nothing || return value
    end
    for key in keys
        value = site_api_payload_get(normalized_payload, String(key), nothing)
        value === nothing || return value
    end
    return default
end


function workbench_bulk_tuning_key(instance, normalized_payload)
    parts = String[
        String(site_api_payload_get(instance, "city", "")),
        lowercase(String(workbench_bulk_tuning_value(instance, normalized_payload, "method", "poi_categories"))),
        string(workbench_bulk_tuning_value(instance, normalized_payload, "seed", 0)),
        String(workbench_bulk_tuning_value(instance, normalized_payload, "depotMode", "center")),
        String(workbench_bulk_tuning_value(instance, normalized_payload, "customerMode", "random_clustered")),
        string(workbench_bulk_tuning_value(instance, normalized_payload, "onlyIntersections", true)),
        string(workbench_bulk_tuning_value(instance, normalized_payload, "clusterSeeds", 4)),
        string(workbench_bulk_tuning_value(instance, normalized_payload, "clusterDecayMeters", 800.0)),
        string(workbench_bulk_tuning_value(instance, normalized_payload, "hybridPoiShare", 0.5)),
        string(workbench_bulk_tuning_value(instance, normalized_payload, "categories", "")),
    ]
    return join(parts, '\u241f')
end


function workbench_bulk_problem_type(instance, normalized_payload)
    value = workbench_bulk_tuning_value_first(instance, normalized_payload, ("problemType", "problem_type"), "CVRP")
    return workbench_normalize_problem_type(value)
end


function workbench_bulk_tw_options(instance, normalized_payload)
    method_raw = workbench_bulk_tuning_value_first(instance, normalized_payload, ("twMethod", "tw_method"), VRPTW_DEFAULT_TW_METHOD)
    horizon_start_raw = workbench_bulk_tuning_value_first(instance, normalized_payload, ("twHorizonStart", "tw_horizon_start"), VRPTW_HORIZON_START)
    horizon_end_raw = workbench_bulk_tuning_value_first(instance, normalized_payload, ("twHorizonEnd", "tw_horizon_end"), VRPTW_HORIZON_END)
    method = workbench_normalize_tw_method(method_raw)
    horizon_start = workbench_normalize_horizon_value(horizon_start_raw, VRPTW_HORIZON_START)
    horizon_end = workbench_normalize_horizon_value(horizon_end_raw, VRPTW_HORIZON_END)
    horizon_end > horizon_start || throw(ArgumentError("twHorizonEnd must be greater than twHorizonStart"))
    return (tw_method=method, horizon_start=horizon_start, horizon_end=horizon_end)
end


function workbench_bulk_match_instance(entry, raw_instances::AbstractVector)
    folder = String(site_api_payload_get(entry, "folder", ""))
    isempty(folder) && return nothing
    summary = site_api_payload_get(entry, "summary", Dict{String,Any}())
    n_customers = Int(site_api_payload_get(summary, "customers", 0))
    base = String(site_api_payload_get(entry, "base_name", ""))
    folder_lower = lowercase(folder)
    for instance in raw_instances
        city_value = site_api_payload_get(instance, "city", "")
        city = lowercase(String(city_value))
        if !isempty(city) && !occursin("/$(city)/", folder_lower)
            continue
        end
        instance_n = Int(site_api_payload_get(instance, "nCustomers", 0))
        if n_customers > 0 && instance_n > 0 && instance_n != n_customers
            continue
        end
        return instance
    end
    isempty(raw_instances) && return nothing
    return first(raw_instances)
end


function workbench_bulk_subpayload(normalized_payload, instances::AbstractVector)
    first_instance = first(instances)
    mutable = Dict{Symbol,Any}()
    for (key, value) in pairs(normalized_payload)
        Symbol(key) == :instances && continue
        mutable[Symbol(key)] = value
    end

    mutable[:instances] = instances
    mutable[:method] = lowercase(String(workbench_bulk_tuning_value(first_instance, normalized_payload, "method", "poi_categories")))
    mutable[:seed] = Int(workbench_bulk_tuning_value(first_instance, normalized_payload, "seed", 0))
    mutable[:depotMode] = String(workbench_bulk_tuning_value(first_instance, normalized_payload, "depotMode", "center"))
    mutable[:customerMode] = String(workbench_bulk_tuning_value(first_instance, normalized_payload, "customerMode", "random_clustered"))
    mutable[:onlyIntersections] = Bool(workbench_bulk_tuning_value(first_instance, normalized_payload, "onlyIntersections", true))
    mutable[:clusterSeeds] = Int(workbench_bulk_tuning_value(first_instance, normalized_payload, "clusterSeeds", 4))
    mutable[:clusterDecayMeters] = Float64(workbench_bulk_tuning_value(first_instance, normalized_payload, "clusterDecayMeters", 800.0))
    mutable[:hybridPoiShare] = Float64(workbench_bulk_tuning_value(first_instance, normalized_payload, "hybridPoiShare", 0.5))
    mutable[:categories] = workbench_bulk_tuning_value(first_instance, normalized_payload, "categories", site_api_payload_get(normalized_payload, "categories", String[]))
    return JSON3.read(JSON3.write(mutable))
end


function workbench_generate_bulk_instances_grouped(normalized_payload)
    raw_instances = site_api_payload_get(normalized_payload, "instances", nothing)
    raw_instances isa AbstractVector || return generate_bulk_instances(normalized_payload)

    grouped_instances = Dict{String,Vector{Any}}()
    group_order = String[]
    for instance in raw_instances
        key = workbench_bulk_tuning_key(instance, normalized_payload)
        if !haskey(grouped_instances, key)
            grouped_instances[key] = Any[]
            push!(group_order, key)
        end
        push!(grouped_instances[key], instance)
    end

    if length(group_order) <= 1
        return generate_bulk_instances(workbench_bulk_subpayload(normalized_payload, raw_instances))
    end

    results = Any[]
    city_reports = Any[]
    for key in group_order
        subpayload = workbench_bulk_subpayload(normalized_payload, grouped_instances[key])
        raw_result = generate_bulk_instances(subpayload)
        append!(results, collect(site_api_payload_get(raw_result, "results", Any[])))
        append!(city_reports, collect(site_api_payload_get(raw_result, "city_reports", Any[])))
    end

    return Dict(
        "ok" => true,
        "count" => length(results),
        "results" => results,
        "city_reports" => city_reports,
    )
end


function workbench_generation_bulk_payload(payload; repo_root::AbstractString=default_site_repo_root())
    isdefined(@__MODULE__, :generate_bulk_instances) || throw(ArgumentError(
        "MAMUT OSM generation helpers are not available; ensure webapp/osm_generation.jl is present"
    ))

    normalized = workbench_normalize_generation_payload(payload, repo_root)
    raw_instances = site_api_payload_get(normalized, "instances", nothing)
    instance_list = raw_instances isa AbstractVector ? collect(raw_instances) : Any[]

    generation_root = canonical_site_repo_root(repo_root)
    raw_result = cd(generation_root) do
        workbench_generate_bulk_instances_grouped(normalized)
    end
    raw_results = site_api_payload_get(raw_result, "results", nothing)
    raw_results isa AbstractVector || throw(ArgumentError("Bulk generation returned no results array"))

    enriched_results = Any[]
    vrptw_count = 0
    for entry in raw_results
        folder = String(site_api_payload_get(entry, "folder", ""))
        base = String(site_api_payload_get(entry, "base_name", ""))
        files_payload = site_api_payload_get(entry, "files", nothing)
        manifest_filename = String(site_api_payload_get(entry, "manifest", ""))
        summary_payload = site_api_payload_get(entry, "summary", Dict{String,Any}())

        artefact = workbench_postprocess_generated_instance(
            repo_root, folder, base, files_payload, manifest_filename, summary_payload,
        )

        matched_instance = workbench_bulk_match_instance(entry, instance_list)
        problem_type = matched_instance === nothing ? "CVRP" :
            workbench_bulk_problem_type(matched_instance, normalized)

        result = Dict{String,Any}(
            "ok" => true,
            "problem_type" => problem_type,
            "base_name" => base,
            "folder" => folder,
            "folder_relative" => artefact.folder_relative,
            "files" => Dict{String,Any}(
                "shortest" => get(artefact.metric_to_filename, "shortest", ""),
                "fastest" => get(artefact.metric_to_filename, "fastest", ""),
                "euclidean" => get(artefact.metric_to_filename, "euclidean", ""),
                "meta" => artefact.meta_filename,
                "manifest" => manifest_filename,
            ),
            "vrp_json_paths" => artefact.vrp_json_paths,
            "manifest" => manifest_filename,
            "summary" => summary_payload,
            "reference_lla" => artefact.reference_lla,
        )

        if problem_type == "VRPTW"
            tw_options = workbench_bulk_tw_options(matched_instance, normalized)
            vrptw_summary = workbench_run_vrptw_post(repo_root, artefact, summary_payload, tw_options)
            if vrptw_summary !== nothing
                result["vrptw"] = vrptw_summary
                vrptw_count += 1
            else
                result["vrptw_error"] = "Cannot derive VRPTW: CVRP fastest variant is missing for $(base)"
            end
        end

        push!(enriched_results, result)
    end

    return Dict(
        "ok" => true,
        "count" => length(enriched_results),
        "vrptw_count" => vrptw_count,
        "results" => enriched_results,
        "city_reports" => site_api_payload_get(raw_result, "city_reports", Any[]),
    )
end


function build_site_api_handler(; repo_root::AbstractString=default_site_repo_root(), api_prefix::AbstractString=DEFAULT_SITE_API_PREFIX, indent::Int=2, sort_keys::Bool=false)
    http = load_http_module()
    resolved_repo_root = canonical_site_repo_root(repo_root)

    return function(request)
        method = String(request.method)
        target = String(request.target)

        if method == "OPTIONS"
            return http.Response(204, site_api_headers())
        end

        path, _ = split_request_target(target)
        if path == "/api/healthz"
            return http.Response(200, site_api_headers(), custom_json_encode(Dict("ok" => true); indent=2, sort_keys=true) * "\n")
        end

        if method == "GET" && path == "/api/workbench/generation/cities"
            try
                return site_api_json_response(200, workbench_generation_cities_payload(resolved_repo_root))
            catch error
                return site_api_json_response(500, Dict("ok" => false, "error" => sprint(showerror, error)))
            end
        end

        if method == "POST" && path == "/api/workbench/generation/fetch-osm-city"
            try
                payload = JSON3.read(String(request.body))
                return site_api_json_response(200, workbench_generation_fetch_osm_city_payload(payload; repo_root=resolved_repo_root))
            catch error
                return site_api_json_response(400, Dict("ok" => false, "error" => sprint(showerror, error)))
            end
        end

        if method == "POST" && path == "/api/workbench/generation/preview"
            try
                payload = materialize_json(JSON3.read(String(request.body)))
                return site_api_json_response(200, workbench_generation_preview_payload(resolved_repo_root, payload))
            catch error
                return site_api_json_response(400, Dict("ok" => false, "error" => sprint(showerror, error)))
            end
        end

        if method == "POST" && path == "/api/workbench/generation/generate"
            try
                payload = JSON3.read(String(request.body))
                return site_api_json_response(200, workbench_generation_full_preview_payload(payload; repo_root=resolved_repo_root))
            catch error
                return site_api_json_response(400, Dict("ok" => false, "error" => sprint(showerror, error)))
            end
        end

        if method == "POST" && path == "/api/workbench/generation/single"
            try
                payload = JSON3.read(String(request.body))
                return site_api_json_response(200, workbench_generation_single_payload(payload; repo_root=resolved_repo_root))
            catch error
                return site_api_json_response(400, Dict("ok" => false, "error" => sprint(showerror, error)))
            end
        end

        if method == "POST" && path == "/api/workbench/generation/bulk"
            try
                payload = JSON3.read(String(request.body))
                return site_api_json_response(200, workbench_generation_bulk_payload(payload; repo_root=resolved_repo_root))
            catch error
                return site_api_json_response(400, Dict("ok" => false, "error" => sprint(showerror, error)))
            end
        end

        if method == "POST" && path == "/api/workbench/solve"
            try
                payload = materialize_json(JSON3.read(String(request.body)))
                return site_api_json_response(200, workbench_solve_hgs_payload(payload))
            catch error
                return site_api_json_response(400, Dict("ok" => false, "error" => sprint(showerror, error)))
            end
        end

        if method == "POST" && path == "/api/workbench/render-routes"
            try
                payload = materialize_json(JSON3.read(String(request.body)))
                return site_api_json_response(200, workbench_render_routes_payload(payload; repo_root=resolved_repo_root))
            catch error
                return site_api_json_response(400, Dict("ok" => false, "error" => sprint(showerror, error)))
            end
        end

        if method != "GET"
            return http.Response(405, site_api_headers(), site_api_error_body("method_not_allowed", "Only GET requests are supported unless a workbench API endpoint is explicitly registered"))
        end

        route_path = extract_site_payload_route(target; api_prefix=api_prefix)
        if route_path !== nothing
            try
                body = render_site_payload_json(resolved_repo_root, route_path; indent=indent, sort_keys=sort_keys) * "\n"
                return http.Response(200, site_api_headers(), body)
            catch error
                if error isa ArgumentError
                    return http.Response(404, site_api_headers(), site_api_error_body("payload_not_found", sprint(showerror, error)))
                end
                return http.Response(500, site_api_headers(), site_api_error_body("internal_error", sprint(showerror, error)))
            end
        end

        try
            static_file = read_site_public_file(resolved_repo_root, target)
            return http.Response(200, site_static_headers(static_file.content_type), static_file.body)
        catch error
            if error isa ArgumentError
                return http.Response(404, site_static_headers("text/plain; charset=utf-8"), sprint(showerror, error) * "\n")
            end
            return http.Response(500, site_static_headers("text/plain; charset=utf-8"), sprint(showerror, error) * "\n")
        end
    end
end


function serve_site_api(; repo_root::AbstractString=default_site_repo_root(), host::AbstractString=DEFAULT_SITE_API_HOST, port::Integer=DEFAULT_SITE_API_PORT, api_prefix::AbstractString=DEFAULT_SITE_API_PREFIX, verbose::Bool=true)
    http = load_http_module()
    handler = build_site_api_handler(; repo_root=repo_root, api_prefix=api_prefix)
    serve_fn = getfield(http, :serve)
    return Base.invokelatest(serve_fn, handler, host, Int(port); verbose=verbose)
end
