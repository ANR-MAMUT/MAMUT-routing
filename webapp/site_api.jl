@isdefined(load_json_site_payload) || include(joinpath(@__DIR__, "io-json-vrp.jl"))

using OpenStreetMapX
using OSMToolset


const DEFAULT_SITE_API_PREFIX = "/api/site-payload"
const DEFAULT_SITE_OUTPUT_ROOT = "dist"
const DEFAULT_SITE_PAYLOAD_ROOT = "site-payloads"
const DEFAULT_SITE_API_HOST = "127.0.0.1"
const DEFAULT_SITE_API_PORT = 8081
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


workbench_route_api_root(repo_root::AbstractString=default_site_repo_root()) =
    normpath(joinpath(canonical_site_repo_root(repo_root), "..", "..", "..", "external", "osm-cvrpgen"))


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
        normpath(joinpath(workbench_route_api_root(repo_root), source_osm_path)),
    ]
    unique!(candidate_paths)

    for candidate_path in candidate_paths
        isfile(candidate_path) && return candidate_path
    end

    throw(ArgumentError("Unable to resolve source OSM file '$(source_osm_path)' for sidecar '$(meta_file_path)'"))
end


function workbench_live_route_coordinates(repo_root::AbstractString, meta_file_path::AbstractString, route::AbstractVector, metric::AbstractString, edge_cache::Dict{String,Vector{Vector{Float64}}})
    metric in ("shortest", "fastest") || throw(ArgumentError("Live road rendering only supports 'shortest' and 'fastest' metrics"))

    meta = load_json_from_file(meta_file_path)
    node_coordinates = workbench_node_coordinates_map(meta)
    graph_vertex_ids = workbench_graph_vertex_id_map(meta)
    depot_node_id = Int(site_api_payload_get(meta, "depot_instance_node_id", 1))
    full_route = [depot_node_id; Int.(collect(route)); depot_node_id]
    length(full_route) >= 2 || throw(ArgumentError("Routes must include at least one customer stop"))
    all(haskey(node_coordinates, node_id) for node_id in full_route) || throw(ArgumentError("Route references unknown instance node ids"))
    all(haskey(graph_vertex_ids, node_id) for node_id in full_route) || throw(ArgumentError("Route references nodes without graph vertex ids in '$(meta_file_path)'"))

    map_options = site_api_payload_get(meta, "map_options", Dict{String,Any}())
    only_intersections = Bool(site_api_payload_get(map_options, "only_intersections", true))
    trim_to_connected_graph = Bool(site_api_payload_get(map_options, "trim_to_connected_graph", true))

    osm_path_ref = Ref{Union{Nothing,String}}(nothing)
    map_data_ref = Ref{Any}(nothing)
    fallback_map_data_ref = Ref{Any}(nothing)
    map_loaded = Ref(false)
    map_unavailable = Ref(false)

    function ensure_map_loaded!()
        (map_loaded[] || map_unavailable[]) && return
        try
            osm_path_ref[] = workbench_resolve_source_osm_path(repo_root, meta, meta_file_path)
            map_data_ref[] = workbench_get_map_data_cached(osm_path_ref[]; only_intersections=only_intersections, trim_to_connected_graph=trim_to_connected_graph)
            if only_intersections
                fallback_map_data_ref[] = workbench_get_map_data_cached(osm_path_ref[]; only_intersections=false, trim_to_connected_graph=trim_to_connected_graph)
            end
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
    vertices = [graph_vertex_ids[node_id] for node_id in full_route]

    for index in 1:(length(vertices) - 1)
        from_vertex = vertices[index]
        to_vertex = vertices[index + 1]
        segment = workbench_cached_segment(edge_cache, from_vertex, to_vertex)
        if segment === nothing
            ensure_map_loaded!()
            if map_loaded[]
                segment = try
                    workbench_segment_coords(map_data_ref[], from_vertex, to_vertex, metric)
                catch error
                    if fallback_map_data_ref[] !== nothing
                        workbench_segment_coords(fallback_map_data_ref[], from_vertex, to_vertex, metric)
                    elseif error isa ArgumentError || error isa KeyError
                        nothing
                    else
                        rethrow(error)
                    end
                end
            end

            if segment === nothing
                segment = workbench_straight_segment(node_coordinates, full_route[index], full_route[index + 1])
                used_straight_fallback = true
                straight_fallback_count += 1
            else
                edge_cache["$(from_vertex)_$(to_vertex)"] = segment
                used_live_routing = true
            end
            cache_miss_count += 1
        else
            used_cache = true
        end

        start_index = index == 1 ? 1 : 2
        append!(route_coordinates, segment[start_index:end])
    end

    render_mode = if used_straight_fallback || (used_live_routing && used_cache)
        "mixed"
    elseif used_live_routing
        "road"
    elseif used_cache
        "cached_road"
    else
        "straight_line"
    end

    return meta, route_coordinates, render_mode, cache_miss_count, used_live_routing, used_straight_fallback, straight_fallback_count
end


function workbench_render_routes_from_meta_path(repo_root::AbstractString, meta_path::AbstractString, routes::AbstractVector, metric::AbstractString)
    metric in ("shortest", "fastest") || throw(ArgumentError("Persistent benchmark rendering only supports 'shortest' and 'fastest' metrics"))

    meta_file_path = workbench_resolve_repo_relative_path(repo_root, meta_path)
    edge_cache = workbench_load_road_cache(meta_file_path, metric)
    features = Any[]
    used_cache = false
    used_live_routing = false
    straight_fallback_count = 0
    cache_miss_count = 0
    meta = nothing

    for (route_index, route) in enumerate(routes)
        meta, coordinates, render_mode, route_cache_misses, route_used_live_routing, route_used_straight_fallback, route_straight_fallback_count = workbench_live_route_coordinates(
            repo_root,
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

    cache_persisted = used_live_routing && cache_miss_count > 0
    cache_persisted && workbench_save_road_cache(meta_file_path, metric, edge_cache)

    render_mode = if straight_fallback_count > 0 || (used_live_routing && used_cache)
        "mixed"
    elseif used_live_routing
        "road"
    elseif used_cache
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
            "straight_fallback_count" => straight_fallback_count,
            "cache_persisted" => cache_persisted,
            "meta_path" => String(meta_path),
        ),
    )
end


function workbench_cached_segment(metric_cache, from_vertex::Int, to_vertex::Int)
    metric_cache isa AbstractDict || return nothing

    forward_key = "$(from_vertex)_$(to_vertex)"
    if haskey(metric_cache, forward_key)
        return [Float64.(collect(point)) for point in metric_cache[forward_key]]
    end

    reverse_key = "$(to_vertex)_$(from_vertex)"
    if haskey(metric_cache, reverse_key)
        reverse_segment = [Float64.(collect(point)) for point in metric_cache[reverse_key]]
        return reverse(reverse_segment)
    end
    return nothing
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
        if metric_cache isa AbstractDict && haskey(graph_vertex_ids, from_node) && haskey(graph_vertex_ids, to_node)
            segment = workbench_cached_segment(metric_cache, graph_vertex_ids[from_node], graph_vertex_ids[to_node])
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
    return normpath(joinpath(canonical_site_repo_root(repo_root), "..", "..", "..", "external", "osm-cvrpgen", "instances_v2", "osm"))
end


function default_workbench_osmdata_root(repo_root::AbstractString=default_site_repo_root())
    return normpath(joinpath(canonical_site_repo_root(repo_root), "..", "..", "..", "external", "osm-cvrpgen", "osmdata"))
end


function workbench_preview_available(repo_root::AbstractString=default_site_repo_root())
    osmdata_root = default_workbench_osmdata_root(repo_root)
    return isdir(osmdata_root) && any(entry -> endswith(lowercase(entry), ".osm"), readdir(osmdata_root))
end


function workbench_city_label(slug::AbstractString)
    return titlecase(replace(String(slug), '-' => ' ', '_' => ' '))
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


function workbench_generation_cities_payload(repo_root::AbstractString=default_site_repo_root(); sample_root::AbstractString=default_workbench_sample_root(repo_root))
    isdir(sample_root) || throw(ArgumentError("Bundled workbench sample root is missing at '$(sample_root)'"))

    cities = Any[]
    for city_dir in sort(filter(isdir, readdir(sample_root; join=true)); by=basename)
        counts = Int[]
        for size_dir in sort(filter(isdir, readdir(city_dir; join=true)); by=basename)
            count = workbench_size_dir_customer_count(size_dir)
            count === nothing || push!(counts, count)
        end
        unique!(counts)
        sort!(counts)
        push!(cities, Dict(
            "slug" => basename(city_dir),
            "label" => workbench_city_label(basename(city_dir)),
            "customer_counts" => counts,
        ))
    end

    return Dict(
        "ok" => true,
        "preview_available" => workbench_preview_available(repo_root),
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
    isdir(sample_root) || throw(ArgumentError("Bundled workbench sample root is missing at '$(sample_root)'"))

    city_slug = lowercase(strip(String(site_api_payload_get(payload, "city", ""))))
    isempty(city_slug) && throw(ArgumentError("Missing required preview field 'city'"))
    requested_method = String(site_api_payload_get(payload, "method", "poi_categories"))
    requested_customers_raw = site_api_payload_get(payload, "nCustomers", site_api_payload_get(payload, "n_customers", nothing))
    requested_customers_raw === nothing && throw(ArgumentError("Missing required preview field 'nCustomers'"))
    requested_customers = Int(requested_customers_raw)

    city_dir = joinpath(sample_root, city_slug)
    isdir(city_dir) || throw(ArgumentError("No bundled sample city matches '$(city_slug)'"))

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

        if method == "POST" && path == "/api/workbench/generation/preview"
            try
                payload = materialize_json(JSON3.read(String(request.body)))
                return site_api_json_response(200, workbench_generation_preview_payload(resolved_repo_root, payload))
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
