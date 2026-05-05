# OSM data import and CVRP instance generation helpers for the MAMUT workbench.
# Kept local so site_api.jl does not depend on another checkout at runtime.
const MAMUT_OSM_GENERATION_HELPERS_LOADED = true

using HTTP
using JSON3
using OpenStreetMapX
using OSMToolset
using DataFrames
using Random
using SparseArrays
using Graphs
using Dates
using UUIDs
using Hygese
import Base.Filesystem: normpath, mkpath
import Base.Threads: lock, unlock

const MAP_CACHE = Dict{String,MapData}()
const VERTEX_LATLON_CACHE = Dict{String,Vector{Tuple{Float64,Float64}}}()

# Progress tracking for long-running operations
const PROGRESS_STATE = Dict{String,Dict{String,Any}}()
const PROGRESS_LOCK = Threads.ReentrantLock()

# Helper functions for progress tracking
function generate_operation_id(operation_type::String)
    return "$(operation_type)_$(UUIDs.uuid4())"
end

function update_progress(operation_id::String, percent::Int, status::String="")
    lock(PROGRESS_LOCK) do
        PROGRESS_STATE[operation_id] = Dict(
            "percent" => clamp(percent, 0, 100),
            "status" => status,
            "timestamp" => time()
        )
    end
end

function get_progress(operation_id::String)
    lock(PROGRESS_LOCK) do
        return get(PROGRESS_STATE, operation_id, nothing)
    end
end

function cleanup_completed_operations(max_age_seconds::Float64=300.0)
    now_time = time()
    lock(PROGRESS_LOCK) do
        for (op_id, progress) in collect(pairs(PROGRESS_STATE))
            if get(progress, "percent", 0) >= 100 && (now_time - get(progress, "timestamp", 0)) > max_age_seconds
                delete!(PROGRESS_STATE, op_id)
            end
        end
    end
end

function send_sse_event(io::IO, op_id::String, percent::Int, status::String="")
    data = Dict("percent" => percent, "status" => status)
    println(io, "data: $(JSON3.write(data))")
    println(io, "")
    flush(io)
end

function cache_key(osm_path::String, only_intersections::Bool, trim_to_connected_graph::Bool)
    return "$(osm_path)|oi=$(only_intersections)|trim=$(trim_to_connected_graph)"
end

function ensure_bounds_from_nodes!(osm_path::String)
    text = read(osm_path, String)
    occursin(r"<bounds\b", text) && return
    # Compute bounds from all <node> lat/lon attributes
    lats = Float64[]
    lons = Float64[]
    for m in eachmatch(r"<node\b[^>]*\blat=\"([^\"]+)\"[^>]*\blon=\"([^\"]+)\"", text)
        push!(lats, parse(Float64, m.captures[1]))
        push!(lons, parse(Float64, m.captures[2]))
    end
    isempty(lats) && error("OSM file '$osm_path' contains no nodes - cannot compute bounds")
    minlat, maxlat = extrema(lats)
    minlon, maxlon = extrema(lons)
    @info "Injecting <bounds> into $osm_path from $(length(lats)) nodes" minlat maxlat minlon maxlon
    ensure_osm_has_bounds!(osm_path, minlat, minlon, maxlat, maxlon)
end

function get_map_data_cached(osm_path::String; only_intersections::Bool=true, trim_to_connected_graph::Bool=true)
    key = cache_key(osm_path, only_intersections, trim_to_connected_graph)
    if haskey(MAP_CACHE, key)
        return MAP_CACHE[key], key
    end

    # Ensure the OSM file has a <bounds> element (required by OpenStreetMapX).
    # Some Overpass API responses omit it; we compute it from node coordinates.
    ensure_bounds_from_nodes!(osm_path)

    # OpenStreetMapX has a bug: when trim_to_connected_graph=true and the graph
    # is already strongly connected (1 component), it calls sum() on an empty range.
    # Also, only_intersections=true can produce empty edge sets for some maps.
    # We try progressively relaxed options until one works.
    fallbacks = [
        (only_intersections, trim_to_connected_graph),
        (only_intersections, false),
        (false, trim_to_connected_graph),
        (false, false),
    ]
    # Deduplicate while preserving order
    seen = Set{Tuple{Bool,Bool}}()
    unique_fallbacks = Tuple{Bool,Bool}[]
    for fb in fallbacks
        if !(fb in seen)
            push!(seen, fb)
            push!(unique_fallbacks, fb)
        end
    end

    local md
    for (i, (oi, ttcg)) in enumerate(unique_fallbacks)
        try
            md = get_map_data(osm_path;
                              use_cache=false,
                              only_intersections=oi,
                              trim_to_connected_graph=ttcg)
            if i > 1
                @warn "Map parsing succeeded with fallback options" osm_path only_intersections=oi trim_to_connected_graph=ttcg
            end
            k = cache_key(osm_path, oi, ttcg)
            MAP_CACHE[k] = md
            MAP_CACHE[key] = md
            return md, k
        catch e
            if e isa ArgumentError && occursin("empty collection", e.msg)
                i < length(unique_fallbacks) && continue
                error("OSM file '$osm_path' produced an empty road graph. The file may lack drivable roads or be too small.")
            end
            rethrow()
        end
    end
end

function get_vertex_latlon(md::MapData, key::String)
    if haskey(VERTEX_LATLON_CACHE, key)
        return VERTEX_LATLON_CACHE[key]
    end
    out = Vector{Tuple{Float64,Float64}}(undef, length(md.n))
    for v in 1:length(md.n)
        osm_id = md.n[v]
        lla = LLA(md.nodes[osm_id], md.bounds)
        out[v] = (lla.lat, lla.lon)
    end
    VERTEX_LATLON_CACHE[key] = out
    return out
end

haversine_m(lat1, lon1, lat2, lon2) = begin
    r = 6371000.0
    dlat = deg2rad(lat2 - lat1)
    dlon = deg2rad(lon2 - lon1)
    a = sin(dlat / 2)^2 + cos(deg2rad(lat1)) * cos(deg2rad(lat2)) * sin(dlon / 2)^2
    return 2r * asin(sqrt(a))
end

function slugify(s::String)
    out = lowercase(strip(s))
    out = replace(out, r"[^a-z0-9]+" => "_")
    out = replace(out, r"_+" => "_")
    out = strip(out, '_')
    return isempty(out) ? "x" : out
end

function build_time_matrix(md::MapData; speeds=SPEED_ROADS_URBAN)
    vertex_count = nv(md.g)
    edge_count = length(md.e)
    rows = Vector{Int}(undef, edge_count)
    cols = Vector{Int}(undef, edge_count)
    values = Vector{Float64}(undef, edge_count)
    Threads.@threads for i in eachindex(md.e)
        osm_u, osm_v = md.e[i]
        u, v = md.v[osm_u], md.v[osm_v]
        dist_m = md.w[u, v]
        spd_mps = speeds[md.class[i]]
        rows[i] = u
        cols[i] = v
        values[i] = 3.6 * dist_m / spd_mps
    end
    return sparse(rows, cols, values, vertex_count, vertex_count)
end

function euclidean_matrix_from_vertices(md::MapData, vertices::Vector{Int}, refLLA)
    n = length(vertices)
    coords = Vector{Tuple{Float64,Float64}}(undef, n)
    for i in 1:n
        osm = md.n[vertices[i]]
        lla = LLA(md.nodes[osm], md.bounds)
        e = ENU(lla, refLLA)
        coords[i] = (getX(e), getY(e))
    end

    D = Matrix{Int}(undef, n, n)
    for i in 1:n, j in 1:n
        dx = coords[i][1] - coords[j][1]
        dy = coords[i][2] - coords[j][2]
        D[i, j] = ceil(Int, sqrt(dx^2 + dy^2))
    end
    return D, coords
end

function parse_routes_from_sol(sol_text::String)
    routes = Vector{Vector{Int}}()
    for line in split(sol_text, '\n')
        m = match(r"^\s*Route\s*#\d+\s*:\s*(.*)$"i, line)
        m === nothing && continue
        stops = parse.(Int, filter(!isempty, split(strip(m.captures[1]))))
        push!(routes, stops)
    end
    isempty(routes) && error("No routes found in solution text")
    return routes
end

function parse_routes(payload)
    if haskey(payload, :routes)
        return [Int.(collect(route)) for route in payload.routes]
    end
    if haskey(payload, :solText)
        return parse_routes_from_sol(String(payload.solText))
    end
    error("Request must contain either 'routes' or 'solText'")
end

function node_map_from_meta(meta)
    out = Dict{Int,Int}()
    for n in meta.nodes
        out[Int(n.instance_node_id)] = Int(n.graph_vertex_id)
    end
    return out
end

function route_demand(route::Vector{Int}, meta)
    demands = Dict{Int,Int}()
    for n in meta.nodes
        demands[Int(n.instance_node_id)] = Int(n.demand)
    end
    return sum((get(demands, c, 0) for c in route); init=0)
end

function segment_coords(md::MapData, from_vertex::Int, to_vertex::Int, metric::String)
    (1 <= from_vertex <= length(md.n)) || error("Graph vertex id $from_vertex is out of bounds for this map")
    (1 <= to_vertex <= length(md.n)) || error("Graph vertex id $to_vertex is out of bounds for this map")
    u_osm = md.n[from_vertex]
    v_osm = md.n[to_vertex]
    if metric == "fastest"
        noderoute, _, _ = fastest_route(md, u_osm, v_osm)
    else
        noderoute, _, _ = shortest_route(md, u_osm, v_osm)
    end
    coords = Vector{Vector{Float64}}()
    for n in noderoute
        lla = LLA(md.nodes[n], md.bounds)
        push!(coords, [lla.lon, lla.lat])
    end
    return coords
end

function path_coords(md::MapData, route_vertices::Vector{Int}, metric::String)
    osm_ids = Int[]
    for v in route_vertices
        (1 <= v <= length(md.n)) || error("Graph vertex id $v is out of bounds for this map")
        push!(osm_ids, md.n[v])
    end

    coords = Vector{Tuple{Float64,Float64}}()
    for i in 1:(length(osm_ids)-1)
        u = osm_ids[i]
        v = osm_ids[i+1]
        if metric == "fastest"
            noderoute, _, _ = fastest_route(md, u, v)
        else
            noderoute, _, _ = shortest_route(md, u, v)
        end

        start_idx = (i == 1) ? 1 : 2
        for n in noderoute[start_idx:end]
            lla = LLA(md.nodes[n], md.bounds)
            push!(coords, (lla.lon, lla.lat))
        end
    end
    return coords
end

function find_meta_file_path(instance_name::String; root::String="instances_v2/osm")
    isdir(root) || return nothing
    target = "$(instance_name)_meta.json"
    for city_dir in readdir(root; join=true)
        isdir(city_dir) || continue
        # Check directly in city_dir (legacy flat layout)
        candidate = joinpath(city_dir, target)
        isfile(candidate) && return candidate
        # Check in size subfolders (new layout: city/n<N>/)
        for size_dir in readdir(city_dir; join=true)
            isdir(size_dir) || continue
            candidate = joinpath(size_dir, target)
            isfile(candidate) && return candidate
        end
    end
    return nothing
end

function load_road_cache(meta_file_path::String, metric::String)
    cache = Dict{String,Vector{Vector{Float64}}}()
    isfile(meta_file_path) || return cache
    raw = JSON3.read(read(meta_file_path, String), Dict{String,Any})
    haskey(raw, "road_cache") || return cache
    rc = raw["road_cache"]
    haskey(rc, metric) || return cache
    for (k, v) in rc[metric]
        cache[String(k)] = v
    end
    return cache
end

function save_road_cache(meta_file_path::String, metric::String, edge_cache::Dict{String,Vector{Vector{Float64}}})
    isfile(meta_file_path) || return
    raw_str = read(meta_file_path, String)
    meta_dict = JSON3.read(raw_str, Dict{String,Any})

    if !haskey(meta_dict, "road_cache")
        meta_dict["road_cache"] = Dict{String,Any}()
    end
    meta_dict["road_cache"][metric] = edge_cache

    open(meta_file_path, "w") do io
        JSON3.pretty(io, JSON3.read(JSON3.write(meta_dict)))
    end
end

function list_osm_cities(osm_dir::String="osmdata")
    isdir(osm_dir) || return String[]
    files = filter(f -> endswith(lowercase(f), ".osm"), readdir(osm_dir))
    cities = [splitext(f)[1] for f in files]
    sort!(cities)
    return cities
end

function parse_string_array(x)
    if x isa AbstractString
        return [strip(s) for s in split(String(x), ',') if !isempty(strip(s))]
    end
    return [String(v) for v in x]
end

function parse_int_array(x)
    if x isa AbstractString
        return [parse(Int, strip(s)) for s in split(String(x), ',') if !isempty(strip(s))]
    end
    return [Int(v) for v in x]
end

function parse_demand_ranges(x)
    if x isa AbstractString
        out = Vector{Tuple{Int,Int}}()
        for part in split(String(x), ';')
            p = strip(part)
            isempty(p) && continue
            m = match(r"^(\d+)\s*[-:]\s*(\d+)$", p)
            m === nothing && error("Invalid range '$p' (expected min-max)")
            lo = parse(Int, m.captures[1])
            hi = parse(Int, m.captures[2])
            lo <= hi || error("Invalid range '$p': min > max")
            push!(out, (lo, hi))
        end
        return out
    end
    out = Vector{Tuple{Int,Int}}()
    for it in x
        lo = Int(it[1]); hi = Int(it[2])
        lo <= hi || error("Invalid range [$lo,$hi]")
        push!(out, (lo, hi))
    end
    return out
end

function pick_depot_vertex(mode::String, vertex_ll::Vector{Tuple{Float64,Float64}}, rng::MersenneTwister)
    N = length(vertex_ll)
    N >= 1 || error("Cannot pick depot from empty vertex list")
    mode == "random" && return rand(rng, 1:N)

    if mode == "center"
        c_lat = sum(t[1] for t in vertex_ll; init=0.0) / N
        c_lon = sum(t[2] for t in vertex_ll; init=0.0) / N
        best_v, best_d = 1, Inf
        for v in 1:N
            lat, lon = vertex_ll[v]
            d = haversine_m(lat, lon, c_lat, c_lon)
            if d < best_d
                best_d = d
                best_v = v
            end
        end
        return best_v
    end

    if mode == "corner"
        min_lat = minimum(t[1] for t in vertex_ll; init=Inf)
        min_lon = minimum(t[2] for t in vertex_ll; init=Inf)
        best_v, best_d = 1, Inf
        for v in 1:N
            lat, lon = vertex_ll[v]
            d = haversine_m(lat, lon, min_lat, min_lon)
            if d < best_d
                best_d = d
                best_v = v
            end
        end
        return best_v
    end

    error("Unsupported depot mode '$mode'")
end

function sample_clustered_vertices(candidates::Vector{Int},
                                   vertex_ll::Vector{Tuple{Float64,Float64}},
                                   target::Int,
                                   n_seeds::Int,
                                   decay_m::Float64,
                                   rng::MersenneTwister)
    target <= 0 && return Int[]
    n_seeds = clamp(n_seeds, 1, max(1, min(target, length(candidates))))
    seeds = rand(rng, candidates, n_seeds)
    selected = Set{Int}(seeds)

    max_weight = 0.0
    for s in seeds
        slat, slon = vertex_ll[s]
        w = 0.0
        for t in seeds
            tlat, tlon = vertex_ll[t]
            w += 2.0 ^ (-haversine_m(slat, slon, tlat, tlon) / decay_m)
        end
        max_weight = max(max_weight, w)
    end
    max_weight = max(max_weight, 1e-9)

    attempts = 0
    max_attempts = max(5000, 300 * target)
    while length(selected) < target && attempts < max_attempts
        attempts += 1
        v = rand(rng, candidates)
        v in selected && continue
        vlat, vlon = vertex_ll[v]
        w = 0.0
        for s in seeds
            slat, slon = vertex_ll[s]
            w += 2.0 ^ (-haversine_m(vlat, vlon, slat, slon) / decay_m)
        end
        p = clamp(w / max_weight, 0.0, 1.0)
        rand(rng) <= p && push!(selected, v)
    end

    if length(selected) < target
        rem = [v for v in candidates if !(v in selected)]
        shuffle!(rng, rem)
        append!(selected, rem[1:min(length(rem), target - length(selected))])
    end

    out = collect(selected)
    shuffle!(rng, out)
    return out[1:min(target, length(out))]
end

function select_customers_parametric(md::MapData,
                                     vertex_ll::Vector{Tuple{Float64,Float64}},
                                     depot_vertex::Int,
                                     n_customers::Int,
                                     customer_mode::String,
                                     n_seeds::Int,
                                     decay_m::Float64,
                                     rng::MersenneTwister)
    candidates = [v for v in 1:length(md.n) if v != depot_vertex]
    isempty(candidates) && error("No candidate vertices in map")
    if n_customers > length(candidates)
        @warn "Requested $n_customers customers but only $(length(candidates)) candidate graph vertices - using all available"
        n_customers = length(candidates)
    end

    selected = Int[]
    if customer_mode == "random"
        selected = rand(rng, candidates, n_customers)
    elseif customer_mode == "clustered"
        selected = sample_clustered_vertices(candidates, vertex_ll, n_customers, n_seeds, decay_m, rng)
    elseif customer_mode == "random_clustered"
        n_rand = div(n_customers, 2)
        rand_part = rand(rng, candidates, n_rand)
        rem_candidates = [v for v in candidates if !(v in rand_part)]
        cl_part = sample_clustered_vertices(rem_candidates, vertex_ll, n_customers - n_rand, n_seeds, decay_m, rng)
        selected = vcat(rand_part, cl_part)
        shuffle!(rng, selected)
    else
        error("Unsupported customer mode '$customer_mode'")
    end

    unique_selected = unique(selected)
    if length(unique_selected) < n_customers
        rem = [v for v in candidates if !(v in unique_selected)]
        shuffle!(rng, rem)
        append!(unique_selected, rem[1:(n_customers - length(unique_selected))])
    end
    return unique_selected[1:n_customers], fill("param", n_customers)
end

function default_categories()
    return ["restaurant", "cafe", "bar", "fast_food", "pub", "school", "university"]
end

function select_customers_poi(md::MapData,
                              osm_path::String,
                              refLLA,
                              n_customers::Int,
                              categories::Vector{String},
                              rng::MersenneTwister)
    cats = isempty(categories) ? default_categories() : categories
    cfg = ScrapePOIConfig{NoneMetaPOI}(DataFrame(key=fill("amenity", length(cats)), values=cats))
    dfpoi = try
        find_poi(osm_path, cfg)
    catch e
        error("POI search failed for categories $(cats): $(sprint(showerror, e))")
    end
    nrow(dfpoi) > 0 || error("No POI found for selected categories: $(join(cats, ", "))")

    ix = NodeSpatIndex(md, refLLA)
    rows = collect(1:nrow(dfpoi))
    shuffle!(rng, rows)

    taken = Set{Int}()
    verts = Int[]
    poi_lats = Float64[]
    poi_lons = Float64[]

    for i in rows
        _, osm_id = findnode(ix, LLA(dfpoi.lat[i], dfpoi.lon[i]))
        if osm_id != 0 && haskey(md.v, osm_id)
            v = md.v[osm_id]
            if !(v in taken)
                push!(taken, v)
                push!(verts, v)
                push!(poi_lats, Float64(dfpoi.lat[i]))
                push!(poi_lons, Float64(dfpoi.lon[i]))
                length(verts) >= n_customers && break
            end
        end
    end

    if length(verts) < n_customers
        @warn "Only found $(length(verts)) POI-attached unique graph vertices; requested $n_customers"
    end
    n_actual = min(n_customers, length(verts))
    return verts[1:n_actual], poi_lats[1:n_actual], poi_lons[1:n_actual], fill("poi", n_actual)
end

function select_customers_hybrid(md::MapData,
                                 osm_path::String,
                                 refLLA,
                                 vertex_ll::Vector{Tuple{Float64,Float64}},
                                 depot_vertex::Int,
                                 n_customers::Int,
                                 categories::Vector{String},
                                 poi_share::Float64,
                                 customer_mode::String,
                                 n_seeds::Int,
                                 decay_m::Float64,
                                 rng::MersenneTwister)
    n_poi = clamp(round(Int, n_customers * poi_share), 0, n_customers)
    n_param = n_customers - n_poi

    poi_v = Int[]
    poi_lat = Float64[]
    poi_lon = Float64[]
    poi_src = String[]
    if n_poi > 0
        pv, plat, plon, psrc = select_customers_poi(md, osm_path, refLLA, n_poi, categories, rng)
        poi_v = pv
        poi_lat = plat
        poi_lon = plon
        poi_src = psrc
    end

    param_v, _ = select_customers_parametric(md, vertex_ll, depot_vertex, max(n_param, 0), customer_mode, n_seeds, decay_m, rng)

    seen = Set{Int}([depot_vertex])
    out_v = Int[]
    out_lat = Float64[]
    out_lon = Float64[]
    out_src = String[]

    for i in 1:lastindex(poi_v)
        v = poi_v[i]
        if !(v in seen)
            push!(seen, v)
            push!(out_v, v)
            push!(out_lat, poi_lat[i])
            push!(out_lon, poi_lon[i])
            push!(out_src, poi_src[i])
        end
    end

    for v in param_v
        if !(v in seen)
            push!(seen, v)
            lat, lon = vertex_ll[v]
            push!(out_v, v)
            push!(out_lat, lat)
            push!(out_lon, lon)
            push!(out_src, "param")
        end
    end

    if length(out_v) < n_customers
        candidates = [v for v in 1:length(md.n) if !(v in seen)]
        shuffle!(rng, candidates)
        for v in candidates
            lat, lon = vertex_ll[v]
            push!(out_v, v)
            push!(out_lat, lat)
            push!(out_lon, lon)
            push!(out_src, "param_fill")
            length(out_v) >= n_customers && break
        end
    end

    length(out_v) >= n_customers || error("Hybrid method could not gather enough unique customers")
    return out_v[1:n_customers], out_lat[1:n_customers], out_lon[1:n_customers], out_src[1:n_customers]
end

function write_cvrplib(fname, name, comment, coords, demands, M::Matrix{Int}, cap)
    open(fname, "w") do io
        println(io, "NAME : $name")
        println(io, "TYPE : CVRP")
        println(io, "COMMENT : $comment")
        println(io, "DIMENSION : ", length(demands))
        println(io, "CAPACITY : $cap")
        println(io, "EDGE_WEIGHT_TYPE : EXPLICIT")
        println(io, "EDGE_WEIGHT_FORMAT : FULL_MATRIX")
        println(io, "EDGE_WEIGHT_SECTION")
        for i in 1:size(M, 1)
            println(io, join(M[i, :], ' '))
        end
        println(io, "NODE_COORD_SECTION")
        for i in 1:lastindex(coords)
            println(io, i, " ", coords[i][1], " ", coords[i][2])
        end
        println(io, "DEMAND_SECTION")
        for i in 1:lastindex(demands)
            println(io, i, " ", demands[i])
        end
        println(io, "DEPOT_SECTION\n1\n-1\nEOF")
    end
end

function write_instance_metadata(meta_path::String,
                                 city::String,
                                 osm_file::String,
                                 instname::String,
                                 metric_files::Vector{String},
                                 refLLA,
                                 vertices::Vector{Int},
                                 poi_lats::Vector{Float64},
                                 poi_lons::Vector{Float64},
                                 coords::Vector{Tuple{Float64,Float64}},
                                 demands::Vector{Int},
                                 method::String,
                                 source_tags::Vector{String};
                                 only_intersections::Bool=true,
                                 trim_to_connected_graph::Bool=true,
                                 generation_params=Dict{String,Any}(),
                                 road_cache=nothing)
    n = length(vertices)
    @assert n == length(coords) == length(demands) == length(poi_lats) == length(poi_lons) == length(source_tags)

    nodes = [Dict(
        "instance_node_id" => i,
        "graph_vertex_id" => vertices[i],
        "poi_lat" => poi_lats[i],
        "poi_lon" => poi_lons[i],
        "enu_x" => coords[i][1],
        "enu_y" => coords[i][2],
        "demand" => demands[i],
        "source_tag" => source_tags[i],
    ) for i in 1:n]

    payload = Dict(
        "schema_version" => 2,
        "city" => city,
        "instance_name" => instname,
        "source_osm_file" => osm_file,
        "metric_files" => metric_files,
        "depot_instance_node_id" => 1,
        "method" => method,
        "reference_lla" => Dict(
            "lat" => Float64(refLLA.lat),
            "lon" => Float64(refLLA.lon),
            "alt" => Float64(refLLA.alt),
        ),
        "map_options" => Dict(
            "only_intersections" => only_intersections,
            "trim_to_connected_graph" => trim_to_connected_graph,
        ),
        "generation_params" => generation_params,
        "nodes" => nodes,
    )

    if road_cache !== nothing
        payload["road_cache"] = road_cache
    end

    open(meta_path, "w") do io
        JSON3.pretty(io, JSON3.read(JSON3.write(payload)))
    end
end

function parse_vrp_for_solve(vrp_text::String)
    dim_m = match(r"DIMENSION\s*:\s*(\d+)"i, vrp_text)
    isnothing(dim_m) && error("Missing DIMENSION header in VRP text")
    dimension = parse(Int, dim_m[1])

    cap_m = match(r"CAPACITY\s*:\s*(\d+)"i, vrp_text)
    isnothing(cap_m) && error("Missing CAPACITY header in VRP text")
    capacity = parse(Int, cap_m[1])

    # Extract weight matrix (EXPLICIT FULL_MATRIX format)
    wt_m = match(r"EDGE_WEIGHT_SECTION\s*\n([\s\S]*?)\nNODE_COORD_SECTION"i, vrp_text)
    isnothing(wt_m) && error("Missing EDGE_WEIGHT_SECTION in VRP text")
    wt_vals = parse.(Float64, split(strip(wt_m[1])))
    length(wt_vals) == dimension * dimension || error("EDGE_WEIGHT_SECTION has $(length(wt_vals)) values, expected $(dimension*dimension)")
    # File is written row-major; reshape then transpose for Julia column-major
    weights = Matrix(reshape(wt_vals, (dimension, dimension))')

    # Extract demands
    dm_m = match(r"DEMAND_SECTION\s*\n([\s\S]*?)\nDEPOT_SECTION"i, vrp_text)
    isnothing(dm_m) && error("Missing DEMAND_SECTION in VRP text")
    demands = zeros(Int, dimension)
    for line in split(strip(dm_m[1]), '\n')
        parts = split(strip(line))
        length(parts) >= 2 || continue
        idx = parse(Int, parts[1])
        demands[idx] = parse(Int, parts[2])
    end

    return dimension, capacity, weights, demands
end

function solve_hgs(vrp_text::String; time_limit::Float64=30.0)
    dimension, capacity, weights, demands = parse_vrp_for_solve(vrp_text)
    @info "Solving CVRP with HGS" dimension capacity time_limit

    ap = AlgorithmParameters(timeLimit=time_limit, seed=Int32(0))
    result = solve_cvrp(weights, demands, capacity, ap; verbose=false)

    # result.routes contains 1-based node indices (depot=1, customers=2..n)
    routes = [Vector{Int}(r) for r in result.routes]

    @info "HGS solve complete" cost=result.cost n_routes=length(routes) time=result.time
    return Dict(
        "ok" => true,
        "cost" => result.cost,
        "time" => result.time,
        "routes" => routes,
        "n_routes" => length(routes),
    )
end

function header_value(vrp_text::String, key::String)
    pat = Regex("^\\s*" * key * "\\s*:\\s*(.+)\$", "im")
    m = match(pat, vrp_text)
    m === nothing && error("Missing $key header in VRP text")
    return strip(String(m.captures[1]))
end

function sanitize_instance_basename(name::AbstractString)
    out = replace(strip(String(name)), r"[^A-Za-z0-9._-]+" => "_")
    out = replace(out, r"_+" => "_")
    out = strip(out, ['_', '.'])
    isempty(out) && error("Invalid VRP NAME header")
    return out
end

function city_slug_from_instance_name(instance_name::AbstractString)
    name = String(instance_name)
    m = match(r"^(.+)_([a-z0-9]+)-n\d+-k\d+"i, name)
    if m !== nothing
        return slugify(String(m.captures[1]))
    end
    parts = split(name, '_')
    city_part = isempty(parts) ? name : parts[1]
    return slugify(city_part)
end

function size_slug_from_instance_name(instance_name::AbstractString)
    m = match(r"-(n\d+)-k\d+"i, String(instance_name))
    m !== nothing && return lowercase(String(m.captures[1]))
    return "unknown"
end

function route_to_customer_indices(route::Vector{Int})
    out = Int[]
    for id in route
        id == 1 && continue
        push!(out, id - 1)
    end
    return out
end

function format_sol_text(routes::Vector{Vector{Int}}; cost=nothing)
    lines = String[]
    for (idx, route) in enumerate(routes)
        customers = route_to_customer_indices(route)
        push!(lines, "Route #$(idx): " * join(customers, ' '))
    end
    if cost !== nothing
        push!(lines, "Cost $(cost)")
    end
    return join(lines, "\n") * "\n"
end

function format_solution_section(routes::Vector{Vector{Int}}; cost=nothing, solve_time=nothing, sol_file::String="")
    lines = String[]
    push!(lines, "SOLUTION_SOURCE : HGS")
    !isempty(sol_file) && push!(lines, "SOLUTION_FILE : $(sol_file)")
    cost !== nothing && push!(lines, "SOLUTION_COST : $(cost)")
    solve_time !== nothing && push!(lines, "SOLUTION_TIME_SEC : $(solve_time)")
    push!(lines, "SOLUTION_SECTION")
    for (idx, route) in enumerate(routes)
        customers = route_to_customer_indices(route)
        push!(lines, "Route #$(idx): " * join(customers, ' '))
    end
    cost !== nothing && push!(lines, "Cost $(cost)")
    push!(lines, "END_SOLUTION")
    return join(lines, "\n") * "\n"
end

function save_hgs_solution_vrp(vrp_text::String,
                               routes::Vector{Vector{Int}};
                               output_root::String="instances_v2",
                               cost=nothing,
                               solve_time=nothing)
    isempty(routes) && error("Cannot save an empty solution")

    dimension_m = match(r"DIMENSION\s*:\s*(\d+)"i, vrp_text)
    dimension_m === nothing && error("Missing DIMENSION header in VRP text")
    dimension = parse(Int, dimension_m[1])
    for (idx, route) in enumerate(routes)
        for id in route
            (2 <= id <= dimension) || error("Route #$(idx) has node id $(id) out of bounds [2,$(dimension)]")
        end
    end

    raw_name = header_value(vrp_text, "NAME")
    instance_name = sanitize_instance_basename(raw_name)
    city_slug = city_slug_from_instance_name(instance_name)
    size_slug = size_slug_from_instance_name(instance_name)
    folder = joinpath(output_root, "osm", city_slug, size_slug)
    mkpath(folder)

    sol_file = "$(instance_name)_hgs.sol"

    sol_text = format_sol_text(routes; cost=cost)
    open(joinpath(folder, sol_file), "w") do io
        write(io, sol_text)
    end

    return Dict(
        "ok" => true,
        "city_slug" => city_slug,
        "folder" => folder,
        "sol_file" => sol_file,
        "sol_path" => joinpath(folder, sol_file),
    )
end

function compute_matrices(md::MapData, vertices::Vector{Int})
    n = length(vertices)
    w_dist = md.w
    w_time = build_time_matrix(md)

    D_short = Matrix{Int}(undef, n, n)
    D_fast = Matrix{Int}(undef, n, n)

    # Per-row results for road geometry (collected after parallel loop)
    edge_geom_shortest = Dict{String,Vector{Vector{Float64}}}()
    edge_geom_fastest = Dict{String,Vector{Vector{Float64}}}()

    # Each row is independent: Dijkstra from vertices[i].
    # We store per-row geometry in thread-local dicts, then merge.
    row_geom_short = Vector{Dict{String,Vector{Vector{Float64}}}}(undef, n)
    row_geom_fast = Vector{Dict{String,Vector{Vector{Float64}}}}(undef, n)

    Threads.@threads for i in 1:n
        src = vertices[i]
        # Run shortest and fastest Dijkstra concurrently
        task_dist = Threads.@spawn dijkstra_shortest_paths(md.g, src, w_dist)
        state_time = dijkstra_shortest_paths(md.g, src, w_time)
        state_dist = fetch(task_dist)

        for k in 1:n
            D_short[i, k] = ceil(Int, state_dist.dists[vertices[k]])
            D_fast[i, k] = ceil(Int, state_time.dists[vertices[k]])
        end

        # Extract road geometry only for depot edges (i==1 or dest==depot)
        local_short = Dict{String,Vector{Vector{Float64}}}()
        local_fast = Dict{String,Vector{Vector{Float64}}}()
        targets = if i == 1
            [k for k in 2:n]
        else
            [1]
        end
        for k in targets
            edge_key = "$(vertices[i])_$(vertices[k])"
            gpath_s = enumerate_paths(state_dist, vertices[k])
            if !isempty(gpath_s)
                seg_s = Vector{Vector{Float64}}()
                for gv in gpath_s
                    osm_id = md.n[gv]
                    lla = LLA(md.nodes[osm_id], md.bounds)
                    push!(seg_s, [lla.lon, lla.lat])
                end
                local_short[edge_key] = seg_s
            end
            gpath_f = enumerate_paths(state_time, vertices[k])
            if !isempty(gpath_f)
                seg_f = Vector{Vector{Float64}}()
                for gv in gpath_f
                    osm_id = md.n[gv]
                    lla = LLA(md.nodes[osm_id], md.bounds)
                    push!(seg_f, [lla.lon, lla.lat])
                end
                local_fast[edge_key] = seg_f
            end
        end
        row_geom_short[i] = local_short
        row_geom_fast[i] = local_fast
    end

    # Merge per-row geometry dicts
    for i in 1:n
        merge!(edge_geom_shortest, row_geom_short[i])
        merge!(edge_geom_fastest, row_geom_fast[i])
    end

    return D_short, D_fast, edge_geom_shortest, edge_geom_fastest
end

function instance_path_plan(city::String,
                            method::String,
                            n_customers::Int,
                            demand_type::Int,
                            avg_route_size::Int,
                            route_count::Int,
                            seed::Int,
                            output_root::String)
    city_slug = slugify(city)
    method_slug = method_abbrev(method)
    n_nodes = n_customers + 1
    folder = joinpath(output_root, "osm", city_slug, "n$(n_nodes)")
    base = "$(city_slug)_$(method_slug)-n$(n_nodes)-k$(route_count)"
    return folder, base
end

function method_abbrev(method::String)
    m = lowercase(strip(method))
    m == "poi_categories" && return "poi"
    m == "parametric_attach" && return "par"
    m == "hybrid" && return "hyb"
    return slugify(m)
end

function getv(payload, key::Symbol, default)
    return haskey(payload, key) ? payload[key] : default
end

function parse_bool(x, default::Bool)
    x === nothing && return default
    x isa Bool && return x
    s = lowercase(String(x))
    s in ("1", "true", "yes", "y", "on") && return true
    s in ("0", "false", "no", "n", "off") && return false
    return default
end

function parse_depot_mode(v)
    if v isa Integer
        return v == 1 ? "random" : v == 2 ? "center" : "corner"
    end
    s = lowercase(String(v))
    s in ("random", "center", "corner") || error("Unsupported depotMode '$s'")
    return s
end

function parse_customer_mode(v)
    if v isa Integer
        return v == 1 ? "random" : v == 2 ? "clustered" : "random_clustered"
    end
    s = lowercase(String(v))
    s in ("random", "clustered", "random_clustered") || error("Unsupported customerMode '$s'")
    return s
end

function demand_distribution_bounds(demand_type::Int)
    demand_type == 1 && return (1, 1)
    demand_type == 2 && return (1, 10)
    demand_type == 3 && return (5, 10)
    demand_type == 4 && return (1, 100)
    demand_type == 5 && return (50, 100)
    demand_type == 6 && return (1, 50)
    demand_type == 7 && return (1, 10)
    error("Demand distribution out of range: $demand_type")
end

function avg_route_size_bounds(avg_route_size::Int)
    avg_route_size == 1 && return (3.0, 5.0)
    avg_route_size == 2 && return (5.0, 8.0)
    avg_route_size == 3 && return (8.0, 12.0)
    avg_route_size == 4 && return (12.0, 16.0)
    avg_route_size == 5 && return (16.0, 25.0)
    avg_route_size == 6 && return (25.0, 50.0)
    avg_route_size == 7 && return (50.0, 200.0)
    error("Average route size out of range: $avg_route_size")
end

function generate_demands(rng::AbstractRNG,
                          customer_ll::Vector{Tuple{Float64,Float64}},
                          demand_type::Int,
                          avg_route_size::Int)
    n = length(customer_ll)
    n >= 1 || error("At least one customer is required")

    rlo, rhi = avg_route_size_bounds(avg_route_size)
    r = rand(rng) * (rhi - rlo) + rlo

    if demand_type == 1
        D = fill(1, n)
        return D, sum(D), maximum(D), r
    end

    lo, hi = demand_distribution_bounds(demand_type)

    D = Vector{Int}(undef, n)
    max_demand = 0
    sum_demands = 0

    # Quadrant split for demand_type == 6.
    lat_center = sum(p[1] for p in customer_ll; init=0.0) / n
    lon_center = sum(p[2] for p in customer_ll; init=0.0) / n

    for i in 1:n
        d = rand(rng, lo:hi)
        if demand_type == 6
            lat, lon = customer_ll[i]
            same_diagonal = ((lat < lat_center && lon < lon_center) || (lat >= lat_center && lon >= lon_center))
            d = same_diagonal ? rand(rng, 51:100) : rand(rng, 1:50)
        elseif demand_type == 7
            if i < (n / r) * 1.5
                d = rand(rng, 50:100)
            else
                d = rand(rng, 1:10)
            end
        end
        D[i] = d
        max_demand = max(max_demand, d)
        sum_demands += d
    end

    if demand_type != 6
        shuffle!(rng, D)
    end

    return D, sum_demands, max_demand, r
end

function capacity_from_avg_route_size(r::Float64, demands::Vector{Int})
    total = sum(demands)
    max_demand = isempty(demands) ? 0 : maximum(demands)
    if total == length(demands)
        return floor(Int, r)
    end
    return max(max_demand, ceil(Int, r * total / length(demands)))
end

function sanitize_city_filename(city::String)
    name = strip(city)
    isempty(name) && error("City name cannot be empty")
    name = replace(name, r"[\\/:*?\"<>|\x00-\x1F]" => "_")
    name = replace(name, r"\s+" => " ")
    name = strip(name)
    name == "." && error("Invalid city name")
    name == ".." && error("Invalid city name")
    return name
end

function fetch_city_bbox(city::String; country::String="")
    q = isempty(strip(country)) ? city : "$(city), $(country)"
    url = "https://nominatim.openstreetmap.org/search?q=$(HTTP.escapeuri(q))&format=json&limit=1"
    resp = HTTP.get(url, ["User-Agent" => "OSM-CVRP-gen/1.0"])
    resp.status == 200 || error("Geocode failed: HTTP $(resp.status)")
    data = JSON3.read(String(resp.body))
    isempty(data) && error("No result found for '$q'")
    bb = data[1]["boundingbox"]
    return (
        parse(Float64, String(bb[1])),
        parse(Float64, String(bb[3])),
        parse(Float64, String(bb[2])),
        parse(Float64, String(bb[4])),
    )
end

const OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

function overpass_error_snippet(body::AbstractString)
    s = replace(String(body), r"\s+" => " ")
    return first(s, min(lastindex(s), 180))
end

function is_retryable_overpass_failure(status::Integer, body::AbstractString)
    status in (408, 429, 500, 502, 503, 504) && return true
    b = lowercase(String(body))
    occursin("dispatcher_client::request_read_and_idx::timeout", b) && return true
    occursin("the server is probably too busy", b) && return true
    occursin("runtime error", b) && occursin("timeout", b) && return true
    return false
end

function build_overpass_query(bbox::String; include_amenities::Bool=true)
    if include_amenities
        return """
        [out:xml][timeout:180][maxsize:1073741824];
        (
          way[\"highway\"]$bbox;
          node[\"amenity\"]$bbox;
        ) -> .sel;
        (
          .sel;
          .sel >;
        );
        out body;
        """
    end

    return """
    [out:xml][timeout:120][maxsize:536870912];
    (
      way[\"highway\"]$bbox;
    ) -> .sel;
    (
      .sel;
      .sel >;
    );
    out body;
    """
end

function try_download_overpass_query!(query::String, outpath::String)
    headers = ["Content-Type" => "text/plain; charset=utf-8", "User-Agent" => "OSM-CVRP-gen/1.0"]
    attempts_per_endpoint = 2
    total_attempts = attempts_per_endpoint * length(OVERPASS_ENDPOINTS)
    attempt_idx = 0
    failures = String[]

    for endpoint in OVERPASS_ENDPOINTS
        for _ in 1:attempts_per_endpoint
            attempt_idx += 1
            try
                resp = HTTP.post(
                    endpoint,
                    headers,
                    query;
                    status_exception=false,
                    connect_timeout=20,
                    readtimeout=220,
                    retry=false,
                )

                body = String(resp.body)
                if resp.status == 200
                    if !occursin("<osm", body)
                        push!(failures, "$(endpoint) -> HTTP 200 but response is not OSM XML")
                    else
                        open(outpath, "w") do io
                            write(io, body)
                        end
                        return true, failures
                    end
                else
                    push!(failures, "$(endpoint) -> HTTP $(resp.status): $(overpass_error_snippet(body))")
                    if !is_retryable_overpass_failure(resp.status, body)
                        return false, failures
                    end
                end
            catch err
                push!(failures, "$(endpoint) -> $(sprint(showerror, err))")
            end

            if attempt_idx < total_attempts
                backoff = min(20.0, 1.7 ^ (attempt_idx - 1)) + rand() * 0.4
                sleep(backoff)
            end
        end
    end

    return false, failures
end

function try_fetch_overpass_body(query::String; attempts_per_endpoint::Int=1, readtimeout::Int=140)
    headers = ["Content-Type" => "text/plain; charset=utf-8", "User-Agent" => "OSM-CVRP-gen/1.0"]
    total_attempts = max(1, attempts_per_endpoint) * length(OVERPASS_ENDPOINTS)
    attempt_idx = 0
    failures = String[]

    for endpoint in OVERPASS_ENDPOINTS
        for _ in 1:max(1, attempts_per_endpoint)
            attempt_idx += 1
            try
                resp = HTTP.post(
                    endpoint,
                    headers,
                    query;
                    status_exception=false,
                    connect_timeout=20,
                    readtimeout=readtimeout,
                    retry=false,
                )

                body = String(resp.body)
                if resp.status == 200
                    occursin("<osm", body) && return body, failures
                    push!(failures, "$(endpoint) -> HTTP 200 but response is not OSM XML")
                else
                    push!(failures, "$(endpoint) -> HTTP $(resp.status): $(overpass_error_snippet(body))")
                    if !is_retryable_overpass_failure(resp.status, body)
                        return nothing, failures
                    end
                end
            catch err
                push!(failures, "$(endpoint) -> $(sprint(showerror, err))")
            end

            if attempt_idx < total_attempts
                backoff = min(8.0, 1.5 ^ (attempt_idx - 1)) + rand() * 0.2
                sleep(backoff)
            end
        end
    end

    return nothing, failures
end

function split_range(minv::Float64, maxv::Float64, max_tile_span::Float64)
    span = maxv - minv
    span <= 0 && return [(minv, maxv)]
    ntiles = max(1, ceil(Int, span / max_tile_span))
    step = span / ntiles
    out = Vector{Tuple{Float64,Float64}}(undef, ntiles)
    for i in 1:ntiles
        lo = minv + (i - 1) * step
        hi = (i == ntiles) ? maxv : (minv + i * step)
        out[i] = (lo, hi)
    end
    return out
end

function extract_node_blocks(osm_text::String)
    blocks = String[]
    # Capture both self-closing nodes and multi-line node blocks.
    pat = r"(?s)<node\b[^>]*\bid=\"-?\d+\"[^>]*/>|<node\b[^>]*\bid=\"-?\d+\"[^>]*>.*?</node>"
    for m in eachmatch(pat, osm_text)
        push!(blocks, m.match)
    end
    return blocks
end

function extract_node_id(node_block::String)
    m = match(r"\bid=\"(-?\d+)\"", node_block)
    return m === nothing ? nothing : parse(Int, m.captures[1])
end

function merge_nodes_into_osm!(osm_path::String, node_blocks::Vector{String})
    isempty(node_blocks) && return 0
    text = read(osm_path, String)

    existing_ids = Set{Int}()
    for m in eachmatch(r"<node\b[^>]*\bid=\"(-?\d+)\"[^>]*>", text)
        push!(existing_ids, parse(Int, m.captures[1]))
    end
    for m in eachmatch(r"<node\b[^>]*\bid=\"(-?\d+)\"[^>]*/>", text)
        push!(existing_ids, parse(Int, m.captures[1]))
    end

    to_add = String[]
    for block in node_blocks
        id = extract_node_id(block)
        id === nothing && continue
        if !(id in existing_ids)
            push!(existing_ids, id)
            push!(to_add, block)
        end
    end
    isempty(to_add) && return 0

    close_tag = "</osm>"
    pos = findlast(close_tag, text)
    pos === nothing && error("Invalid OSM file (missing </osm>): $osm_path")
    tag_start = first(pos)

    merged_nodes = "\n" * join(to_add, "\n") * "\n"
    newtext = text[1:prevind(text, tag_start)] * merged_nodes * text[tag_start:end]
    open(osm_path, "w") do io
        write(io, newtext)
    end
    return length(to_add)
end

function fetch_tiled_amenities!(minlat::Float64, minlon::Float64, maxlat::Float64, maxlon::Float64, outpath::String)
    lat_tiles = split_range(minlat, maxlat, 0.03)
    lon_tiles = split_range(minlon, maxlon, 0.04)
    total_tiles = length(lat_tiles) * length(lon_tiles)
    total_tiles > 0 || return Dict("ok" => false, "tiles_total" => 0, "tiles_ok" => 0, "amenity_nodes_added" => 0)

    all_blocks = String[]
    tiles_ok = 0
    failures = String[]

    for (lat_lo, lat_hi) in lat_tiles
        for (lon_lo, lon_hi) in lon_tiles
            bbox = "($lat_lo,$lon_lo,$lat_hi,$lon_hi)"
            q = """
            [out:xml][timeout:75][maxsize:268435456];
            (
              node[\"amenity\"]$bbox;
            );
            out body;
            """
            body, tile_failures = try_fetch_overpass_body(q; attempts_per_endpoint=1, readtimeout=120)
            if body === nothing
                append!(failures, tile_failures)
                continue
            end

            append!(all_blocks, extract_node_blocks(body))
            tiles_ok += 1
        end
    end

    added = merge_nodes_into_osm!(outpath, all_blocks)
    return Dict(
        "ok" => tiles_ok > 0,
        "tiles_total" => total_tiles,
        "tiles_ok" => tiles_ok,
        "amenity_nodes_added" => added,
        "failure_count" => length(failures),
    )
end

function download_osm_bbox!(minlat::Float64, minlon::Float64, maxlat::Float64, maxlon::Float64, outpath::String; operation_id::String="")
    bbox = "($minlat,$minlon,$maxlat,$maxlon)"
    if !isempty(operation_id)
        update_progress(operation_id, 0, "Starting OSM download")
    end
    
    ok_full, failures_full = try_download_overpass_query!(build_overpass_query(bbox; include_amenities=true), outpath)
    if !isempty(operation_id)
        update_progress(operation_id, 50, "Downloaded roads and amenities")
    end
    
    ok_full && return "roads_and_amenities"

    ok_roads, failures_roads = try_download_overpass_query!(build_overpass_query(bbox; include_amenities=false), outpath)
    if !isempty(operation_id)
        update_progress(operation_id, 70, "Downloaded roads only")
    end
    
    ok_roads && return "roads_only"

    summary_full = isempty(failures_full) ? "no details" : join(failures_full, " | ")
    summary_roads = isempty(failures_roads) ? "no details" : join(failures_roads, " | ")
    error("Overpass unavailable for both queries. roads+amenities failures: $(summary_full) || roads-only failures: $(summary_roads)")
end

function ensure_osm_has_bounds!(filepath::String,
                                minlat::Float64,
                                minlon::Float64,
                                maxlat::Float64,
                                maxlon::Float64)
    text = read(filepath, String)
    occursin(r"<bounds", text) && return
    m = match(r"<osm\b[^>]*>", text)
    m === nothing && error("No <osm> tag in $filepath")
    tag_end = m.offset + length(m.match) - 1
    bounds_line = "<bounds minlat=\"$minlat\" minlon=\"$minlon\" maxlat=\"$maxlat\" maxlon=\"$maxlon\"/>"
    newtext = text[1:tag_end] * "\n  " * bounds_line * "\n" * text[tag_end+1:end]
    open(filepath, "w") do io
        write(io, newtext)
    end
end

function fetch_and_store_city_osm(payload; operation_id::String="")
    city = String(getv(payload, :city, ""))
    isempty(strip(city)) && error("Missing 'city'")
    country = String(getv(payload, :country, ""))
    osm_dir = String(getv(payload, :osmDir, "osmdata"))
    padding_km = Float64(getv(payload, :paddingKm, 0.0))

    safe_city = sanitize_city_filename(city)
    mkpath(osm_dir)
    outpath = joinpath(osm_dir, "$(safe_city).osm")

    minlat, minlon, maxlat, maxlon = fetch_city_bbox(city; country=country)
    if padding_km > 0
        dlat = padding_km / 111.0
        mean_lat = (minlat + maxlat) / 2
        dlon = padding_km / max(1e-6, 111.0 * cosd(mean_lat))
        minlat -= dlat
        maxlat += dlat
        minlon -= dlon
        maxlon += dlon
    end

    dataset_mode = download_osm_bbox!(minlat, minlon, maxlat, maxlon, outpath; operation_id=operation_id)
    if !isempty(operation_id)
        update_progress(operation_id, 80, "Processing OSM data")
    end
    
    amenity_tiling = Dict(
        "ok" => false,
        "tiles_total" => 0,
        "tiles_ok" => 0,
        "amenity_nodes_added" => 0,
        "failure_count" => 0,
    )

    if dataset_mode == "roads_only"
        amenity_tiling = fetch_tiled_amenities!(minlat, minlon, maxlat, maxlon, outpath)
        if get(amenity_tiling, "ok", false) && Int(get(amenity_tiling, "amenity_nodes_added", 0)) > 0
            dataset_mode = "roads_plus_tiled_amenities"
        end
    end

    ensure_osm_has_bounds!(outpath, minlat, minlon, maxlat, maxlon)

    # Clear relevant map cache entries for this file so fresh content is used immediately.
    for k in collect(keys(MAP_CACHE))
        if startswith(k, outpath * "|")
            delete!(MAP_CACHE, k)
            haskey(VERTEX_LATLON_CACHE, k) && delete!(VERTEX_LATLON_CACHE, k)
        end
    end

    if !isempty(operation_id)
        update_progress(operation_id, 100, "OSM data ready")
    end

    return Dict(
        "ok" => true,
        "city" => safe_city,
        "osm_path" => outpath,
        "dataset_mode" => dataset_mode,
        "amenity_tiling" => amenity_tiling,
        "warning" => dataset_mode == "roads_only" ? "Amenities could not be fetched from Overpass (including tiled fallback); POI-based generation may have fewer candidates." : "",
        "bbox" => Dict(
            "minlat" => minlat,
            "minlon" => minlon,
            "maxlat" => maxlat,
            "maxlon" => maxlon,
        ),
        "cities" => list_osm_cities(osm_dir),
    )
end

function build_generation_selection(payload)
    city = String(getv(payload, :city, ""))
    isempty(city) && error("Missing 'city'")

    osm_path = String(getv(payload, :osmPath, joinpath("osmdata", "$(city).osm")))
    isfile(osm_path) || error("OSM file not found: $osm_path")

    method = lowercase(String(getv(payload, :method, "poi_categories")))
    method in ("poi_categories", "parametric_attach", "hybrid") || error("Unsupported method '$method'")

    n_customers = Int(getv(payload, :nCustomers, 50))
    n_customers >= 2 || error("nCustomers must be >= 2")

    demand_type = Int(getv(payload, :demandType, 7))
    avg_route_size = Int(getv(payload, :avgRouteSize, 4))

    seed = Int(getv(payload, :seed, 0))
    rng = MersenneTwister(seed)

    only_intersections = parse_bool(getv(payload, :onlyIntersections, true), true)
    trim_connected = parse_bool(getv(payload, :trimToConnectedGraph, true), true)

    md, key = get_map_data_cached(osm_path;
                                  only_intersections=only_intersections,
                                  trim_to_connected_graph=trim_connected)
    refLLA = OpenStreetMapX.center(md.bounds)
    vertex_ll = get_vertex_latlon(md, key)

    depot_mode = parse_depot_mode(getv(payload, :depotMode, "center"))
    customer_mode = parse_customer_mode(getv(payload, :customerMode, "random_clustered"))
    n_seeds = Int(getv(payload, :clusterSeeds, rand(rng, 2:6)))
    decay_m = Float64(getv(payload, :clusterDecayMeters, 800.0))
    categories = haskey(payload, :categories) ? parse_string_array(payload[:categories]) : default_categories()
    hybrid_poi_share = clamp(Float64(getv(payload, :hybridPoiShare, 0.5)), 0.0, 1.0)

    depot_vertex = pick_depot_vertex(depot_mode, vertex_ll, rng)
    depot_lat, depot_lon = vertex_ll[depot_vertex]

    cust_vertices = Int[]
    cust_poi_lat = Float64[]
    cust_poi_lon = Float64[]
    cust_sources = String[]

    if method == "poi_categories"
        v, lat, lon, src = select_customers_poi(md, osm_path, refLLA, n_customers, categories, rng)
        cust_vertices = [x for x in v if x != depot_vertex]
        cust_poi_lat = lat[1:length(cust_vertices)]
        cust_poi_lon = lon[1:length(cust_vertices)]
        cust_sources = src[1:length(cust_vertices)]
        if length(cust_vertices) < n_customers
            rem_vertices, rem_src = select_customers_parametric(md, vertex_ll, depot_vertex, n_customers - length(cust_vertices), customer_mode, n_seeds, decay_m, rng)
            append!(cust_vertices, rem_vertices)
            for vtx in rem_vertices
                latv, lonv = vertex_ll[vtx]
                push!(cust_poi_lat, latv)
                push!(cust_poi_lon, lonv)
            end
            append!(cust_sources, rem_src)
        end
    elseif method == "parametric_attach"
        v, src = select_customers_parametric(md, vertex_ll, depot_vertex, n_customers, customer_mode, n_seeds, decay_m, rng)
        cust_vertices = v
        cust_sources = src
        for vtx in cust_vertices
            latv, lonv = vertex_ll[vtx]
            push!(cust_poi_lat, latv)
            push!(cust_poi_lon, lonv)
        end
    else
        v, lat, lon, src = select_customers_hybrid(md, osm_path, refLLA, vertex_ll, depot_vertex, n_customers, categories, hybrid_poi_share, customer_mode, n_seeds, decay_m, rng)
        cust_vertices = v
        cust_poi_lat = lat
        cust_poi_lon = lon
        cust_sources = src
    end

    length(cust_vertices) >= n_customers || @warn "Generation method produced only $(length(cust_vertices)) customers out of requested $n_customers"
    n_actual = min(n_customers, length(cust_vertices))
    cust_vertices = cust_vertices[1:n_actual]
    cust_poi_lat = cust_poi_lat[1:n_actual]
    cust_poi_lon = cust_poi_lon[1:n_actual]
    cust_sources = cust_sources[1:n_actual]

    vertices = vcat([depot_vertex], cust_vertices)
    poi_lats = vcat([depot_lat], cust_poi_lat)
    poi_lons = vcat([depot_lon], cust_poi_lon)
    source_tags = vcat(["depot"], cust_sources)

    params = Dict(
        "city" => city,
        "osm_path" => osm_path,
        "method" => method,
        "n_customers" => n_customers,
        "seed" => seed,
        "demand_type" => demand_type,
        "avg_route_size" => avg_route_size,
        "depot_mode" => depot_mode,
        "customer_mode" => customer_mode,
        "cluster_seeds" => n_seeds,
        "cluster_decay_meters" => decay_m,
        "categories" => categories,
        "hybrid_poi_share" => hybrid_poi_share,
        "only_intersections" => only_intersections,
        "trim_to_connected_graph" => trim_connected,
    )

    return Dict(
        "md" => md,
        "refLLA" => refLLA,
        "vertices" => vertices,
        "poi_lats" => poi_lats,
        "poi_lons" => poi_lons,
        "source_tags" => source_tags,
        "params" => params,
    )
end

function preview_geojson(selection)
    md = selection["md"]
    vertices = selection["vertices"]
    sources = selection["source_tags"]

    feats = Any[]
    for i in 1:lastindex(vertices)
        v = vertices[i]
        osm_id = md.n[v]
        lla = LLA(md.nodes[osm_id], md.bounds)
        push!(feats, Dict(
            "type" => "Feature",
            "geometry" => Dict("type" => "Point", "coordinates" => [lla.lon, lla.lat]),
            "properties" => Dict(
                "instance_node_id" => i,
                "graph_vertex_id" => v,
                "role" => i == 1 ? "depot" : "customer",
                "source_tag" => sources[i],
            )
        ))
    end

    return Dict("type" => "FeatureCollection", "features" => feats)
end

function generate_single_instance(payload)
    sel = build_generation_selection(payload)
    n_requested = Int(getv(payload, :nCustomers, 50))
    n_got = length(sel["vertices"]) - 1   # minus depot
    n_got >= n_requested || error("Generation method produced only $n_got customers out of requested $n_requested")
    md = sel["md"]
    refLLA = sel["refLLA"]
    vertices = sel["vertices"]
    poi_lats = sel["poi_lats"]
    poi_lons = sel["poi_lons"]
    source_tags = sel["source_tags"]
    params = sel["params"]

    output_root = String(getv(payload, :outputRoot, "instances_v2"))
    demand_type = Int(getv(payload, :demandType, 7))
    avg_route_size = Int(getv(payload, :avgRouteSize, 4))

    demand_type in 1:7 || error("demandType must be between 1 and 7")
    avg_route_size in 1:7 || error("avgRouteSize must be between 1 and 7")

    rng = MersenneTwister(Int(params["seed"]))
    customer_ll = collect(zip(poi_lats[2:end], poi_lons[2:end]))
    D, sum_demands, _, r = generate_demands(rng, customer_ll, demand_type, avg_route_size)
    demands = vcat([0], D)
    cap = capacity_from_avg_route_size(r, D)
    route_count = ceil(Int, sum_demands / float(cap))

    D_short, D_fast, edge_geom_shortest, edge_geom_fastest = compute_matrices(md, vertices)
    D_eucl, coords = euclidean_matrix_from_vertices(md, vertices, refLLA)

    folder, base = instance_path_plan(String(params["city"]), String(params["method"]), Int(params["n_customers"]), demand_type, avg_route_size, route_count, Int(params["seed"]), output_root)
    mkpath(folder)

    f_short = base * "_shortest.vrp"
    f_fast = base * "_fastest.vrp"
    f_eucl = base * "_euclidean.vrp"
    f_meta = base * "_meta.json"
    f_manifest = base * "_manifest.json"

    write_cvrplib(joinpath(folder, f_short), base * "_shortest", "Shortest distances; ENU ref: $refLLA", coords, demands, D_short, cap)
    write_cvrplib(joinpath(folder, f_fast), base * "_fastest", "Fastest distances; ENU ref: $refLLA", coords, demands, D_fast, cap)
    write_cvrplib(joinpath(folder, f_eucl), base * "_euclidean", "Euclidean distances; ENU ref: $refLLA", coords, demands, D_eucl, cap)

    write_instance_metadata(joinpath(folder, f_meta),
                            String(params["city"]),
                            String(params["osm_path"]),
                            base,
                            [f_short, f_fast, f_eucl],
                            refLLA,
                            vertices,
                            poi_lats,
                            poi_lons,
                            coords,
                            demands,
                            String(params["method"]),
                            source_tags;
                            only_intersections=Bool(params["only_intersections"]),
                            trim_to_connected_graph=Bool(params["trim_to_connected_graph"]),
                            generation_params=params,
                            road_cache=Dict("shortest" => edge_geom_shortest, "fastest" => edge_geom_fastest))

    manifest = Dict(
        "generated_at" => string(Dates.now()),
        "base_name" => base,
        "folder" => folder,
        "files" => Dict(
            "shortest" => f_short,
            "fastest" => f_fast,
            "euclidean" => f_eucl,
            "meta" => f_meta,
        ),
        "params" => params,
        "demand_type" => demand_type,
        "avg_route_size" => avg_route_size,
        "route_count" => route_count,
        "capacity" => cap,
        "total_demand" => sum_demands,
    )
    open(joinpath(folder, f_manifest), "w") do io
        JSON3.pretty(io, JSON3.read(JSON3.write(manifest)))
    end

    poi_count = count(t -> t == "poi", source_tags[2:end])
    param_count = length(source_tags) - 1 - poi_count

    return Dict(
        "ok" => true,
        "base_name" => base,
        "folder" => folder,
        "files" => manifest["files"],
        "manifest" => f_manifest,
        "summary" => Dict(
            "customers" => Int(params["n_customers"]),
            "capacity" => cap,
            "total_demand" => sum_demands,
            "method" => String(params["method"]),
            "demand_type" => demand_type,
            "avg_route_size" => avg_route_size,
            "route_count" => route_count,
            "poi_customers" => poi_count,
            "parametric_customers" => param_count,
        ),
    )
end

function generate_bulk_instances(payload)
    # --- Detect explicit instance list vs legacy Cartesian mode ---
    if haskey(payload, :instances)
        return generate_bulk_instances_explicit(payload)
    end

    # Legacy Cartesian product mode
    cities = haskey(payload, :cities) ? parse_string_array(payload.cities) : [String(getv(payload, :city, ""))]
    cities = [c for c in cities if !isempty(c)]
    isempty(cities) && error("Bulk generation requires at least one city")

    n_list = haskey(payload, :nCustomersList) ? parse_int_array(payload.nCustomersList) : [Int(getv(payload, :nCustomers, 50))]
    d_list = haskey(payload, :demandTypesList) ? parse_int_array(payload.demandTypesList) : [Int(getv(payload, :demandType, 7))]
    r_list = haskey(payload, :avgRouteSizesList) ? parse_int_array(payload.avgRouteSizesList) : [Int(getv(payload, :avgRouteSize, 4))]

    base_seed = Int(getv(payload, :seed, 0))
    output_root = String(getv(payload, :outputRoot, "instances_v2"))
    results = Any[]
    city_reports = Any[]

    for city in cities
        max_nc = maximum(n_list)
        poi_pool_size = ceil(Int, max_nc * 1.5)

        # --- 1) Build POI selection once with about 1.5x max customers for diversity ---
        p_max = Dict{Symbol,Any}()
        for k in keys(payload)
            p_max[k] = payload[k]
        end
        p_max[:city] = city
        p_max[:nCustomers] = poi_pool_size
        p_max[:seed] = Int(hash((city, max_nc, base_seed)) % UInt(typemax(Int64)))

        sel = build_generation_selection(p_max)
        md            = sel["md"]
        refLLA        = sel["refLLA"]
        all_vertices  = sel["vertices"]       # [depot, cust1, ..., cust_pool]
        all_poi_lats  = sel["poi_lats"]
        all_poi_lons  = sel["poi_lons"]
        all_source_tags = sel["source_tags"]
        params_base   = sel["params"]
        total         = length(all_vertices)   # pool + 1 (depot)

        # Detect available POIs and filter requested sizes
        actual_max_nc = total - 1
        @info "Bulk: city $city has $actual_max_nc POIs available (requested pool: $poi_pool_size)"
        valid_n_list = filter(nc -> nc <= actual_max_nc, n_list)
        skipped_sizes = filter(nc -> nc > actual_max_nc, n_list)
        if !isempty(skipped_sizes)
            @warn "City $city: skipping sizes $(skipped_sizes) - only $actual_max_nc POIs available"
        end
        if isempty(valid_n_list)
            @warn "City $city: no valid sizes - skipping city entirely"
            push!(city_reports, Dict(
                "city" => city,
                "poi_available" => 0,
                "parametric_filled" => 0,
                "requested_sizes" => n_list,
                "valid_sizes" => Int[],
                "skipped_sizes" => n_list,
                "status" => "skipped",
            ))
            continue
        end

        # Report POI vs parametric breakdown for the pool
        pool_poi_count = count(t -> t == "poi", all_source_tags[2:end])
        pool_param_count = actual_max_nc - pool_poi_count
        if pool_param_count > 0
            @warn "City $city: POI pool has $pool_poi_count pure POI + $pool_param_count parametric-filled customers (out of $actual_max_nc total)"
        else
            @info "City $city: all $actual_max_nc customers are POI-sourced"
        end

        push!(city_reports, Dict(
            "city" => city,
            "poi_available" => pool_poi_count,
            "parametric_filled" => pool_param_count,
            "pool_total" => actual_max_nc,
            "requested_sizes" => n_list,
            "valid_sizes" => valid_n_list,
            "skipped_sizes" => skipped_sizes,
            "status" => isempty(skipped_sizes) ? "ok" : "partial",
        ))

        # --- 2) Precompute full distance matrices once ---
        @info "Bulk: computing distance matrices for $city ($total vertices)..."
        D_short_full, D_fast_full, edge_geom_short_full, edge_geom_fast_full = compute_matrices(md, all_vertices)
        D_eucl_full, coords_full = euclidean_matrix_from_vertices(md, all_vertices, refLLA)
        @info "Bulk: matrices ready for $city"

        # --- 3) Loop over parameter combos, slicing from precomputed matrices ---
        for nc in valid_n_list
            for dt in d_list
                for ars in r_list
                    inst_seed = Int(hash((city, nc, dt, ars, base_seed)) % UInt(typemax(Int64)))
                    rng = MersenneTwister(inst_seed)

                    # Sample nc customers from the full pool (depot stays at index 1)
                    if nc < actual_max_nc
                        cust_perm = randperm(rng, actual_max_nc)
                        cust_sel = sort(cust_perm[1:nc])
                        sel_indices = vcat([1], cust_sel .+ 1)
                    else
                        sel_indices = collect(1:total)
                    end

                    # Slice matrices
                    M_s = D_short_full[sel_indices, sel_indices]
                    M_f = D_fast_full[sel_indices, sel_indices]
                    M_e = D_eucl_full[sel_indices, sel_indices]
                    coords = coords_full[sel_indices]
                    vertices = all_vertices[sel_indices]
                    poi_lats = all_poi_lats[sel_indices]
                    poi_lons = all_poi_lons[sel_indices]
                    source_tags = all_source_tags[sel_indices]

                    # Filter road geometry to subset vertices
                    subset_verts = Set(vertices)
                    edge_geom_shortest = Dict{String,Vector{Vector{Float64}}}()
                    edge_geom_fastest  = Dict{String,Vector{Vector{Float64}}}()
                    for (ek, ev) in edge_geom_short_full
                        parts = split(ek, '_')
                        u, v = parse(Int, parts[1]), parse(Int, parts[2])
                        if u in subset_verts && v in subset_verts
                            edge_geom_shortest[ek] = ev
                        end
                    end
                    for (ek, ev) in edge_geom_fast_full
                        parts = split(ek, '_')
                        u, v = parse(Int, parts[1]), parse(Int, parts[2])
                        if u in subset_verts && v in subset_verts
                            edge_geom_fastest[ek] = ev
                        end
                    end

                    # Generate demands for the selected subset
                    customer_ll = collect(zip(poi_lats[2:end], poi_lons[2:end]))
                    D, sum_demands, _, r = generate_demands(rng, customer_ll, dt, ars)
                    demands = vcat([0], D)
                    cap = capacity_from_avg_route_size(r, D)
                    route_count = ceil(Int, sum_demands / float(cap))

                    # Write instance files
                    folder, base = instance_path_plan(city, String(params_base["method"]), nc, dt, ars, route_count, inst_seed, output_root)
                    mkpath(folder)

                    f_short    = base * "_shortest.vrp"
                    f_fast     = base * "_fastest.vrp"
                    f_eucl     = base * "_euclidean.vrp"
                    f_meta     = base * "_meta.json"
                    f_manifest = base * "_manifest.json"

                    write_cvrplib(joinpath(folder, f_short), base * "_shortest", "Shortest distances; ENU ref: $refLLA", coords, demands, M_s, cap)
                    write_cvrplib(joinpath(folder, f_fast),  base * "_fastest",  "Fastest distances; ENU ref: $refLLA",  coords, demands, M_f, cap)
                    write_cvrplib(joinpath(folder, f_eucl),  base * "_euclidean","Euclidean distances; ENU ref: $refLLA", coords, demands, M_e, cap)

                    params = copy(params_base)
                    params["n_customers"] = nc
                    params["seed"] = inst_seed
                    params["demand_type"] = dt
                    params["avg_route_size"] = ars

                    write_instance_metadata(joinpath(folder, f_meta),
                                            city,
                                            String(params_base["osm_path"]),
                                            base,
                                            [f_short, f_fast, f_eucl],
                                            refLLA,
                                            vertices,
                                            poi_lats,
                                            poi_lons,
                                            coords,
                                            demands,
                                            String(params_base["method"]),
                                            source_tags;
                                            only_intersections=Bool(params_base["only_intersections"]),
                                            trim_to_connected_graph=Bool(params_base["trim_to_connected_graph"]),
                                            generation_params=params,
                                            road_cache=Dict("shortest" => edge_geom_shortest, "fastest" => edge_geom_fastest))

                    manifest = Dict(
                        "generated_at" => string(Dates.now()),
                        "base_name" => base,
                        "folder" => folder,
                        "files" => Dict(
                            "shortest" => f_short,
                            "fastest"  => f_fast,
                            "euclidean" => f_eucl,
                            "meta"     => f_meta,
                        ),
                        "params" => params,
                        "demand_type" => dt,
                        "avg_route_size" => ars,
                        "route_count" => route_count,
                        "capacity" => cap,
                        "total_demand" => sum_demands,
                    )
                    open(joinpath(folder, f_manifest), "w") do io
                        JSON3.pretty(io, JSON3.read(JSON3.write(manifest)))
                    end

                    # Count POI vs parametric in this instance's subset
                    inst_poi = count(t -> t == "poi", source_tags[2:end])
                    inst_param = nc - inst_poi
                    if inst_param > 0
                        @info "  -> $base: $inst_poi POI + $inst_param parametric customers"
                    end

                    push!(results, Dict(
                        "ok" => true,
                        "base_name" => base,
                        "folder" => folder,
                        "files" => manifest["files"],
                        "manifest" => f_manifest,
                        "summary" => Dict(
                            "customers" => nc,
                            "capacity" => cap,
                            "total_demand" => sum_demands,
                            "method" => String(params_base["method"]),
                            "demand_type" => dt,
                            "avg_route_size" => ars,
                            "route_count" => route_count,
                            "poi_customers" => inst_poi,
                            "parametric_customers" => inst_param,
                        ),
                    ))
                end
            end
        end
    end

    return Dict(
        "ok" => true,
        "count" => length(results),
        "results" => results,
        "city_reports" => city_reports,
    )
end

function generate_bulk_instances_explicit(payload)
    raw_instances = payload.instances
    output_root = String(getv(payload, :outputRoot, "instances_v2"))
    shared_categories = haskey(payload, :categories) ? parse_string_array(payload.categories) : default_categories()
    shared_hybrid_share = Float64(getv(payload, :hybridPoiShare, 0.5))
    shared_only_intersections = parse_bool(getv(payload, :onlyIntersections, true), true)
    shared_cluster_seeds = Int(getv(payload, :clusterSeeds, 4))
    shared_cluster_decay = Float64(getv(payload, :clusterDecayMeters, 800.0))

    # Parse and validate each instance
    instances = Any[]
    for (idx, raw) in enumerate(raw_instances)
        city = String(getv(raw, :city, ""))
        isempty(city) && error("Instance $idx: missing 'city'")
        nc = Int(getv(raw, :nCustomers, 50))
        nc >= 2 || error("Instance $idx: nCustomers must be >= 2")
        dt = Int(getv(raw, :demandType, 7))
        dt in 1:7 || error("Instance $idx: demandType must be 1-7")
        ars = Int(getv(raw, :avgRouteSize, 4))
        ars in 1:7 || error("Instance $idx: avgRouteSize must be 1-7")
        method = lowercase(String(getv(raw, :method, "poi_categories")))
        method in ("poi_categories", "parametric_attach", "hybrid") || error("Instance $idx: unsupported method '$method'")
        seed = Int(getv(raw, :seed, 0))
        depot_mode = String(getv(raw, :depotMode, "center"))
        customer_mode = String(getv(raw, :customerMode, "random_clustered"))
        push!(instances, Dict(
            "city" => city, "nCustomers" => nc, "demandType" => dt, "avgRouteSize" => ars,
            "method" => method, "seed" => seed, "depotMode" => depot_mode, "customerMode" => customer_mode,
        ))
    end
    isempty(instances) && error("No instances provided")

    # Group instances by (city, method) for pool reuse
    city_groups = Dict{String,Vector{Any}}()
    for inst in instances
        city = inst["city"]
        if !haskey(city_groups, city)
            city_groups[city] = Any[]
        end
        push!(city_groups[city], inst)
    end

    results = Any[]
    city_reports = Any[]

    for (city, city_insts) in city_groups
        max_nc = maximum(inst["nCustomers"] for inst in city_insts)
        poi_pool_size = ceil(Int, max_nc * 1.5)

        # Build POI pool once per city using the first instance's method as default
        first_inst = city_insts[1]
        base_seed = first_inst["seed"]
        p_max = Dict{Symbol,Any}(
            :city => city,
            :method => first_inst["method"],
            :nCustomers => poi_pool_size,
            :seed => Int(hash((city, max_nc, base_seed)) % UInt(typemax(Int64))),
            :onlyIntersections => shared_only_intersections,
            :depotMode => first_inst["depotMode"],
            :customerMode => first_inst["customerMode"],
            :clusterSeeds => shared_cluster_seeds,
            :clusterDecayMeters => shared_cluster_decay,
            :categories => shared_categories,
            :hybridPoiShare => shared_hybrid_share,
        )

        sel = build_generation_selection(p_max)
        md            = sel["md"]
        refLLA        = sel["refLLA"]
        all_vertices  = sel["vertices"]
        all_poi_lats  = sel["poi_lats"]
        all_poi_lons  = sel["poi_lons"]
        all_source_tags = sel["source_tags"]
        params_base   = sel["params"]
        total         = length(all_vertices)
        actual_max_nc = total - 1

        @info "Bulk explicit: city $city has $actual_max_nc POIs available (requested pool: $poi_pool_size)"

        n_list_for_city = unique([inst["nCustomers"] for inst in city_insts])
        valid_n_list = filter(nc -> nc <= actual_max_nc, n_list_for_city)
        skipped_sizes = filter(nc -> nc > actual_max_nc, n_list_for_city)

        pool_poi_count = count(t -> t == "poi", all_source_tags[2:end])
        pool_param_count = actual_max_nc - pool_poi_count

        push!(city_reports, Dict(
            "city" => city,
            "poi_available" => pool_poi_count,
            "parametric_filled" => pool_param_count,
            "pool_total" => actual_max_nc,
            "valid_sizes" => sort(valid_n_list),
            "skipped_sizes" => sort(skipped_sizes),
            "status" => isempty(skipped_sizes) ? "ok" : (isempty(valid_n_list) ? "skipped" : "partial"),
        ))

        if isempty(valid_n_list)
            @warn "City $city: no valid sizes - skipping city entirely"
            continue
        end

        # Precompute full distance matrices once per city
        @info "Bulk explicit: computing distance matrices for $city ($total vertices)..."
        D_short_full, D_fast_full, edge_geom_short_full, edge_geom_fast_full = compute_matrices(md, all_vertices)
        D_eucl_full, coords_full = euclidean_matrix_from_vertices(md, all_vertices, refLLA)
        @info "Bulk explicit: matrices ready for $city"

        # Process each instance for this city
        for inst in city_insts
            nc = inst["nCustomers"]
            dt = inst["demandType"]
            ars = inst["avgRouteSize"]
            inst_method = inst["method"]
            inst_seed = Int(hash((city, nc, dt, ars, inst["seed"])) % UInt(typemax(Int64)))

            if nc > actual_max_nc
                @warn "City $city: skipping n=$nc - only $actual_max_nc POIs available"
                continue
            end

            rng = MersenneTwister(inst_seed)

            # Sample nc customers from the full pool
            if nc < actual_max_nc
                cust_perm = randperm(rng, actual_max_nc)
                cust_sel = sort(cust_perm[1:nc])
                sel_indices = vcat([1], cust_sel .+ 1)
            else
                sel_indices = collect(1:total)
            end

            # Slice matrices
            M_s = D_short_full[sel_indices, sel_indices]
            M_f = D_fast_full[sel_indices, sel_indices]
            M_e = D_eucl_full[sel_indices, sel_indices]
            coords = coords_full[sel_indices]
            vertices = all_vertices[sel_indices]
            poi_lats = all_poi_lats[sel_indices]
            poi_lons = all_poi_lons[sel_indices]
            source_tags = all_source_tags[sel_indices]

            # Filter road geometry to subset vertices
            subset_verts = Set(vertices)
            edge_geom_shortest = Dict{String,Vector{Vector{Float64}}}()
            edge_geom_fastest  = Dict{String,Vector{Vector{Float64}}}()
            for (ek, ev) in edge_geom_short_full
                parts = split(ek, '_')
                u, v = parse(Int, parts[1]), parse(Int, parts[2])
                if u in subset_verts && v in subset_verts
                    edge_geom_shortest[ek] = ev
                end
            end
            for (ek, ev) in edge_geom_fast_full
                parts = split(ek, '_')
                u, v = parse(Int, parts[1]), parse(Int, parts[2])
                if u in subset_verts && v in subset_verts
                    edge_geom_fastest[ek] = ev
                end
            end

            # Generate demands
            customer_ll = collect(zip(poi_lats[2:end], poi_lons[2:end]))
            D, sum_demands, _, r = generate_demands(rng, customer_ll, dt, ars)
            demands = vcat([0], D)
            cap = capacity_from_avg_route_size(r, D)
            route_count = ceil(Int, sum_demands / float(cap))

            # Write instance files
            folder, base = instance_path_plan(city, inst_method, nc, dt, ars, route_count, inst_seed, output_root)
            mkpath(folder)

            f_short    = base * "_shortest.vrp"
            f_fast     = base * "_fastest.vrp"
            f_eucl     = base * "_euclidean.vrp"
            f_meta     = base * "_meta.json"
            f_manifest = base * "_manifest.json"

            write_cvrplib(joinpath(folder, f_short), base * "_shortest", "Shortest distances; ENU ref: $refLLA", coords, demands, M_s, cap)
            write_cvrplib(joinpath(folder, f_fast),  base * "_fastest",  "Fastest distances; ENU ref: $refLLA",  coords, demands, M_f, cap)
            write_cvrplib(joinpath(folder, f_eucl),  base * "_euclidean","Euclidean distances; ENU ref: $refLLA", coords, demands, M_e, cap)

            params = copy(params_base)
            params["n_customers"] = nc
            params["seed"] = inst_seed
            params["demand_type"] = dt
            params["avg_route_size"] = ars
            params["method"] = inst_method
            params["depot_mode"] = inst["depotMode"]
            params["customer_mode"] = inst["customerMode"]

            write_instance_metadata(joinpath(folder, f_meta),
                                    city,
                                    String(params_base["osm_path"]),
                                    base,
                                    [f_short, f_fast, f_eucl],
                                    refLLA,
                                    vertices,
                                    poi_lats,
                                    poi_lons,
                                    coords,
                                    demands,
                                    inst_method,
                                    source_tags;
                                    only_intersections=shared_only_intersections,
                                    trim_to_connected_graph=Bool(params_base["trim_to_connected_graph"]),
                                    generation_params=params,
                                    road_cache=Dict("shortest" => edge_geom_shortest, "fastest" => edge_geom_fastest))

            manifest = Dict(
                "generated_at" => string(Dates.now()),
                "base_name" => base,
                "folder" => folder,
                "files" => Dict(
                    "shortest" => f_short,
                    "fastest"  => f_fast,
                    "euclidean" => f_eucl,
                    "meta"     => f_meta,
                ),
                "params" => params,
                "demand_type" => dt,
                "avg_route_size" => ars,
                "route_count" => route_count,
                "capacity" => cap,
                "total_demand" => sum_demands,
            )
            open(joinpath(folder, f_manifest), "w") do io
                JSON3.pretty(io, JSON3.read(JSON3.write(manifest)))
            end

            inst_poi = count(t -> t == "poi", source_tags[2:end])
            inst_param = nc - inst_poi

            push!(results, Dict(
                "ok" => true,
                "base_name" => base,
                "folder" => folder,
                "files" => manifest["files"],
                "manifest" => f_manifest,
                "summary" => Dict(
                    "customers" => nc,
                    "capacity" => cap,
                    "total_demand" => sum_demands,
                    "method" => inst_method,
                    "demand_type" => dt,
                    "avg_route_size" => ars,
                    "route_count" => route_count,
                    "poi_customers" => inst_poi,
                    "parametric_customers" => inst_param,
                ),
            ))
        end
    end

    return Dict(
        "ok" => true,
        "count" => length(results),
        "results" => results,
        "city_reports" => city_reports,
    )
end
