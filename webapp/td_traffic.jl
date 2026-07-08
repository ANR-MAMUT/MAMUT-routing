# Time-dependent traffic stage for the workbench (stage 3 of the generation
# pipeline). Produces per-edge hourly speed profiles over a 24 h day from two
# traffic models and exports the "TD bridge": plain-JSON intermediates the
# Python TD builder (mamut_routing_publish.td_generation) turns into
# TDVRP/TDVRPTW instances of the road-graph td model.
#
# Traffic models:
#   - "bpr":  synthetic commuter population. Homes are sampled uniformly on
#     the graph vertices, workplaces from amenity POIs when available; each
#     commuter fires a morning home->work trip, an evening work->home trip
#     and, with probability 0.25, a lunch round trip. Trips are routed on the
#     free-flow fastest path, per-edge hourly flows are accumulated at the
#     edge ENTRY time (clock advanced with free-flow times along the path),
#     and hourly speeds follow the BPR volume-delay function
#     t = t_free * (1 + 0.15 * (flow/capacity)^4), multiplier capped.
#   - "wave": no simulation. Each edge gets a bimodal rush-hour speed dip
#     scaled by road class, distance to the city centre and a seeded
#     per-edge jitter.
#
# The bridge is a git-ignored intermediate: the canonical data is whatever
# the Python builder freezes into the road-graph sidecars (speeds are
# rounded here to limit sidecar size). Julia RNG drift across versions only
# affects regeneration of intermediates, never published hashed artifacts.
#
# Expected to be include()d after osm_generation.jl (uses
# get_map_data_cached, SPEED_ROADS_URBAN, haversine_m, get_vertex_latlon,
# default_categories).

const TD_BRIDGE_SCHEMA_VERSION = 2
const TD_NUM_BINS = 24
const TD_BIN_SECONDS = 3600.0
const TD_SPEED_DECIMALS = 3          # exported speeds are rounded to mm/s
const TD_MIN_SPEED_FACTOR = 0.12     # never slower than this fraction of free flow

# BPR parameters (Bureau of Public Roads volume-delay function).
const TD_BPR_ALPHA = 0.15
const TD_BPR_BETA = 4
const TD_BPR_MULTIPLIER_CAP = 6.0
# Practical hourly capacity (veh/h) per OpenStreetMapX road class
# (1 motorway, 2 trunk, 3 primary, 4 secondary, 5 tertiary, 6 residential,
# 7 service, 8 living street / pedestrian).
const TD_CAPACITY_VEH_H = Dict(
    1 => 1900.0, 2 => 1600.0, 3 => 1400.0, 4 => 1100.0,
    5 => 900.0, 6 => 600.0, 7 => 400.0, 8 => 300.0,
)
# Commuters per graph vertex, per intensity level. Calibrated on Lyon
# (~27k vertices) so that "heavy" (~270k commuters) yields a metropolitan
# rush hour: arterial corridors visibly slowed at peak, side streets mostly
# free-flowing; "light" only stresses the busiest corridors.
const TD_BPR_TRIPS_PER_VERTEX = Dict("light" => 2.5, "moderate" => 5.0, "heavy" => 10.0)

# Wave-model amplitude (peak relative speed drop on central arterials).
const TD_WAVE_AMPLITUDE = Dict("light" => 0.25, "moderate" => 0.45, "heavy" => 0.65)
const TD_WAVE_JITTER = 0.08
const TD_WAVE_CENTER_DECAY_M = 3000.0
const TD_WAVE_FLOOR_SHARE = 0.35     # peripheral edges still see this share of the dip

const TD_MODELS = ("bpr", "wave")
const TD_INTENSITIES = ("light", "moderate", "heavy")

struct TDBridgeEdge
    u::Int            # internal vertex ids (md numbering)
    v::Int
    osm_u::Int        # OSM node ids (the bridge's stable keys)
    osm_v::Int
    length_m::Float64
    class::Int
end

"Deduplicated directed edge list: one entry per (u, v), keeping the fastest
free-flow representative (max class speed, then min length)."
function td_collect_edges(md::MapData)
    best = Dict{Tuple{Int,Int},TDBridgeEdge}()
    for i in eachindex(md.e)
        osm_u, osm_v = md.e[i]
        u, v = md.v[osm_u], md.v[osm_v]
        u == v && continue
        length_m = md.w[u, v]
        length_m > 0 || continue
        class = md.class[i]
        edge = TDBridgeEdge(u, v, osm_u, osm_v, Float64(length_m), Int(class))
        key = (u, v)
        if haskey(best, key)
            old = best[key]
            new_time = edge.length_m / SPEED_ROADS_URBAN[edge.class]
            old_time = old.length_m / SPEED_ROADS_URBAN[old.class]
            if new_time < old_time || (new_time == old_time && edge.length_m < old.length_m)
                best[key] = edge
            end
        else
            best[key] = edge
        end
    end
    edges = collect(values(best))
    sort!(edges, by=e -> (e.u, e.v))
    return edges
end

td_free_speed_ms(class::Int) = SPEED_ROADS_URBAN[class] / 3.6

td_round_speed(v::Float64) = max(round(v, digits=TD_SPEED_DECIMALS), 10.0^(-TD_SPEED_DECIMALS))

"Bimodal rush-hour curve at bin center, in [0, 1]."
function td_rush_curve(bin::Int)
    h = bin - 0.5
    g = exp(-((h - 8.25)^2) / (2 * 1.1^2)) + 0.85 * exp(-((h - 17.75)^2) / (2 * 1.5^2))
    return min(g, 1.0)
end

# ---------------------------------------------------------------------------
# wave model
# ---------------------------------------------------------------------------

function td_wave_speeds(md::MapData, edges::Vector{TDBridgeEdge}, vertex_ll,
                        intensity::String, seed::Int)
    amplitude = TD_WAVE_AMPLITUDE[intensity]
    center_lat = sum(ll[1] for ll in vertex_ll) / length(vertex_ll)
    center_lon = sum(ll[2] for ll in vertex_ll) / length(vertex_ll)
    rng = MersenneTwister(seed)
    speeds = Vector{Vector{Float64}}(undef, length(edges))
    for (index, edge) in enumerate(edges)
        jitter = (2.0 * rand(rng) - 1.0) * TD_WAVE_JITTER
        mid_lat = (vertex_ll[edge.u][1] + vertex_ll[edge.v][1]) / 2
        mid_lon = (vertex_ll[edge.u][2] + vertex_ll[edge.v][2]) / 2
        centrality = exp(-haversine_m(mid_lat, mid_lon, center_lat, center_lon) / TD_WAVE_CENTER_DECAY_M)
        dip_share = TD_WAVE_FLOOR_SHARE + (1.0 - TD_WAVE_FLOOR_SHARE) * centrality
        free = td_free_speed_ms(edge.class)
        profile = Vector{Float64}(undef, TD_NUM_BINS)
        for bin in 1:TD_NUM_BINS
            dip = amplitude * td_rush_curve(bin) * dip_share
            v = free * (1.0 - dip) * (1.0 + jitter)
            profile[bin] = td_round_speed(max(v, free * TD_MIN_SPEED_FACTOR))
        end
        speeds[index] = profile
    end
    return speeds
end

# ---------------------------------------------------------------------------
# bpr model
# ---------------------------------------------------------------------------

"Workplace vertex pool: amenity-POI-snapped vertices when the OSM file has
enough of them, otherwise all vertices (uniform fallback)."
function td_work_pool(md::MapData, osm_path::String, refLLA)
    cats = default_categories()
    pool = Int[]
    try
        cfg = ScrapePOIConfig{NoneMetaPOI}(DataFrame(key=fill("amenity", length(cats)), values=cats))
        dfpoi = find_poi(osm_path, cfg)
        if nrow(dfpoi) > 0
            ix = NodeSpatIndex(md, refLLA)
            seen = Set{Int}()
            for i in 1:nrow(dfpoi)
                _, osm_id = findnode(ix, LLA(dfpoi.lat[i], dfpoi.lon[i]))
                if osm_id != 0 && haskey(md.v, osm_id)
                    vertex = md.v[osm_id]
                    if !(vertex in seen)
                        push!(seen, vertex)
                        push!(pool, vertex)
                    end
                end
            end
        end
    catch e
        @warn "POI workplace pool failed; falling back to uniform workplaces" exception = sprint(showerror, e)
    end
    length(pool) >= 50 ? sort!(pool) : collect(1:nv(md.g))
end

"Draw a departure hour from a normal, clamped into the day."
td_departure_s(rng, mu_h, sigma_h) = clamp(mu_h + sigma_h * randn(rng), 0.25, 23.75) * TD_BIN_SECONDS

function td_bpr_speeds(md::MapData, edges::Vector{TDBridgeEdge}, osm_path::String,
                       refLLA, intensity::String, seed::Int)
    num_vertices = nv(md.g)
    rng = MersenneTwister(seed)
    commuters = round(Int, TD_BPR_TRIPS_PER_VERTEX[intensity] * num_vertices)
    work_pool = td_work_pool(md, osm_path, refLLA)

    # Trip list: (origin, destination, departure seconds).
    trips = Vector{Tuple{Int,Int,Float64}}()
    sizehint!(trips, 5 * commuters ÷ 2)
    for _ in 1:commuters
        home = rand(rng, 1:num_vertices)
        work = work_pool[rand(rng, 1:length(work_pool))]
        work == home && continue
        push!(trips, (home, work, td_departure_s(rng, 8.0, 0.75)))
        push!(trips, (work, home, td_departure_s(rng, 17.5, 1.0)))
        if rand(rng) < 0.25
            push!(trips, (work, home, td_departure_s(rng, 12.25, 0.5)))
            push!(trips, (home, work, td_departure_s(rng, 13.5, 0.5)))
        end
    end

    # Free-flow travel time weights on the deduplicated edge set.
    edge_index = Dict{Tuple{Int,Int},Int}((e.u, e.v) => i for (i, e) in enumerate(edges))
    rows = [e.u for e in edges]
    cols = [e.v for e in edges]
    times = [e.length_m / td_free_speed_ms(e.class) for e in edges]
    time_mtx = sparse(rows, cols, times, num_vertices, num_vertices)

    # Route trips grouped by origin (one Dijkstra per distinct origin),
    # accumulating per-edge flows at the edge entry time.
    by_origin = Dict{Int,Vector{Tuple{Int,Float64}}}()
    for (origin, destination, departure) in trips
        push!(get!(by_origin, origin, Vector{Tuple{Int,Float64}}()), (destination, departure))
    end
    origins = sort!(collect(keys(by_origin)))
    num_chunks = max(Threads.nthreads(), 1)
    flows_per_chunk = [zeros(Float64, length(edges), TD_NUM_BINS) for _ in 1:num_chunks]
    Threads.@threads for chunk in 1:num_chunks
        chunk_flows = flows_per_chunk[chunk]
        for origin_index in chunk:num_chunks:length(origins)
            origin = origins[origin_index]
            state = Graphs.dijkstra_shortest_paths(md.g, origin, time_mtx)
            for (destination, departure) in by_origin[origin]
                state.dists[destination] < Inf || continue
                path = Graphs.enumerate_paths(state, destination)
                length(path) >= 2 || continue
                clock = departure
                for k in 1:(length(path) - 1)
                    index = get(edge_index, (path[k], path[k + 1]), 0)
                    index == 0 && break
                    bin = clamp(floor(Int, clock / TD_BIN_SECONDS) + 1, 1, TD_NUM_BINS)
                    chunk_flows[index, bin] += 1.0
                    clock += times[index]
                end
            end
        end
    end
    flows = sum(flows_per_chunk)

    speeds = Vector{Vector{Float64}}(undef, length(edges))
    for (index, edge) in enumerate(edges)
        free = td_free_speed_ms(edge.class)
        capacity = get(TD_CAPACITY_VEH_H, edge.class, 600.0)
        profile = Vector{Float64}(undef, TD_NUM_BINS)
        for bin in 1:TD_NUM_BINS
            multiplier = min(1.0 + TD_BPR_ALPHA * (flows[index, bin] / capacity)^TD_BPR_BETA,
                             TD_BPR_MULTIPLIER_CAP)
            profile[bin] = td_round_speed(max(free / multiplier, free * TD_MIN_SPEED_FACTOR))
        end
        speeds[index] = profile
    end
    return speeds, length(trips)
end

# ---------------------------------------------------------------------------
# bridge export
# ---------------------------------------------------------------------------

function td_bridge_seed(base_seed::Int, model::String, intensity::String)
    model_index = findfirst(==(model), TD_MODELS)
    intensity_index = findfirst(==(intensity), TD_INTENSITIES)
    return base_seed + 101 * model_index + 10007 * intensity_index
end

function td_write_json(path::String, payload)
    # Per-process tmp name: concurrent exporters targeting the same city
    # directory (e.g. one per intensity on a shared filesystem) must not
    # rename each other's tmp file away.
    tmp = path * ".tmp.$(getpid())"
    open(tmp, "w") do io
        JSON3.write(io, payload)
    end
    mv(tmp, path; force=true)
end

"""
    export_td_bridge(; osm_path, city_slug, out_root, kwargs...)

Write the TD bridge for one city under `<out_root>/<city_slug>/`:
`graph.json` (deduplicated directed edges keyed by OSM node ids),
`speeds-<model>-<intensity>.json` for every requested combination (speed
profiles aligned with the graph edge order, m/s), one
`nodes-<instance_base>.json` per stage-1 meta file (instance node -> OSM
node ids, depot first) and a `bridge-manifest.json`. Atomic per-file writes
(tmp + rename); existing per-combination speed files are reused unless
`force=true`.
"""
function export_td_bridge(; osm_path::String,
                          city_slug::String,
                          out_root::String,
                          models::Vector{String}=collect(TD_MODELS),
                          intensities::Vector{String}=collect(TD_INTENSITIES),
                          seed::Int=42,
                          meta_paths::Vector{String}=String[],
                          only_intersections::Bool=true,
                          trim_to_connected_graph::Bool=true,
                          force::Bool=false)
    all(m -> m in TD_MODELS, models) || error("unknown traffic model in $(models); known: $(TD_MODELS)")
    all(i -> i in TD_INTENSITIES, intensities) || error("unknown intensity in $(intensities); known: $(TD_INTENSITIES)")

    md, _ = get_map_data_cached(osm_path; only_intersections=only_intersections,
                                trim_to_connected_graph=trim_to_connected_graph)
    vertex_ll = get_vertex_latlon(md, cache_key(osm_path, only_intersections, trim_to_connected_graph))
    center_lla = LLA(sum(ll[1] for ll in vertex_ll) / length(vertex_ll),
                     sum(ll[2] for ll in vertex_ll) / length(vertex_ll))
    edges = td_collect_edges(md)
    out_dir = joinpath(out_root, city_slug)
    mkpath(out_dir)

    # Bridge schema v2 (Stream 12'): edges carry the static free-flow limit
    # (m/s, same rounding as the speed profiles) so the Python builder never
    # needs the class table, and every vertex incident to an edge ships its
    # WGS84 position ([osm_id, lon, lat], sorted by osm_id) for the road-graph
    # v2 `vertex_lonlat` and the geo road cache.
    used_vertices = sort!(collect(Set(v for e in edges for v in (e.u, e.v))))
    graph_path = joinpath(out_dir, "graph.json")
    td_write_json(graph_path, Dict(
        "schema_version" => TD_BRIDGE_SCHEMA_VERSION,
        "city" => city_slug,
        "osm_file" => basename(osm_path),
        "map_options" => Dict(
            "only_intersections" => only_intersections,
            "trim_to_connected_graph" => trim_to_connected_graph,
        ),
        "num_bins" => TD_NUM_BINS,
        "bin_seconds" => TD_BIN_SECONDS,
        "speed_unit" => "m/s",
        "length_unit" => "m",
        "vertices" => [Any[md.n[v], vertex_ll[v][2], vertex_ll[v][1]] for v in used_vertices],
        "edges" => [Any[e.osm_u, e.osm_v, e.length_m, e.class,
                        td_round_speed(td_free_speed_ms(e.class))] for e in edges],
    ))

    written = String[]
    for model in models, intensity in intensities
        speeds_path = joinpath(out_dir, "speeds-$(model)-$(intensity).json")
        if isfile(speeds_path) && !force
            push!(written, basename(speeds_path) * " (kept)")
            continue
        end
        combo_seed = td_bridge_seed(seed, model, intensity)
        trips = 0
        speeds = if model == "wave"
            td_wave_speeds(md, edges, vertex_ll, intensity, combo_seed)
        else
            profile, trips = td_bpr_speeds(md, edges, osm_path, center_lla, intensity, combo_seed)
            profile
        end
        @assert length(speeds) == length(edges)
        td_write_json(speeds_path, Dict(
            "schema_version" => TD_BRIDGE_SCHEMA_VERSION,
            "city" => city_slug,
            "model" => model,
            "intensity" => intensity,
            "seed" => combo_seed,
            "num_trips" => trips,
            "params" => td_model_params(model, intensity),
            "speeds" => speeds,
        ))
        push!(written, basename(speeds_path))
    end

    node_files = String[]
    for meta_path in meta_paths
        meta = JSON3.read(read(meta_path, String))
        base = String(meta["instance_name"])
        node_osm_ids = [md.n[node["graph_vertex_id"]] for node in meta["nodes"]]
        nodes_path = joinpath(out_dir, "nodes-$(base).json")
        td_write_json(nodes_path, Dict(
            "schema_version" => TD_BRIDGE_SCHEMA_VERSION,
            "city" => city_slug,
            "instance_base" => base,
            "depot_first" => true,
            "node_osm_ids" => node_osm_ids,
        ))
        push!(node_files, basename(nodes_path))
    end

    td_write_json(joinpath(out_dir, "bridge-manifest.json"), Dict(
        "schema_version" => TD_BRIDGE_SCHEMA_VERSION,
        "city" => city_slug,
        "num_vertices" => nv(md.g),
        "num_edges" => length(edges),
        "speed_files" => written,
        "node_files" => node_files,
    ))
    return out_dir
end

function td_model_params(model::String, intensity::String)
    if model == "wave"
        return Dict(
            "amplitude" => TD_WAVE_AMPLITUDE[intensity],
            "jitter" => TD_WAVE_JITTER,
            "center_decay_m" => TD_WAVE_CENTER_DECAY_M,
            "floor_share" => TD_WAVE_FLOOR_SHARE,
            "min_speed_factor" => TD_MIN_SPEED_FACTOR,
        )
    end
    return Dict(
        "trips_per_vertex" => TD_BPR_TRIPS_PER_VERTEX[intensity],
        "bpr_alpha" => TD_BPR_ALPHA,
        "bpr_beta" => TD_BPR_BETA,
        "multiplier_cap" => TD_BPR_MULTIPLIER_CAP,
        "capacity_veh_h" => TD_CAPACITY_VEH_H,
        "min_speed_factor" => TD_MIN_SPEED_FACTOR,
        "departures" => Dict(
            "morning" => [8.0, 0.75], "evening" => [17.5, 1.0],
            "lunch_return" => [12.25, 0.5], "lunch_back" => [13.5, 0.5],
            "lunch_probability" => 0.25,
        ),
    )
end

"JSON-config entry point for non-interactive runs (the Python CLI drives this)."
function run_td_bridge_export(config_path::String)
    config = JSON3.read(read(config_path, String))
    out_dir = export_td_bridge(;
        osm_path=String(config["osm_path"]),
        city_slug=String(config["city_slug"]),
        out_root=String(config["out_root"]),
        models=[String(m) for m in get(config, "models", collect(TD_MODELS))],
        intensities=[String(i) for i in get(config, "intensities", collect(TD_INTENSITIES))],
        seed=Int(get(config, "seed", 42)),
        meta_paths=[String(p) for p in get(config, "meta_paths", String[])],
        only_intersections=Bool(get(config, "only_intersections", true)),
        trim_to_connected_graph=Bool(get(config, "trim_to_connected_graph", true)),
        force=Bool(get(config, "force", false)),
    )
    println("TD bridge written to $(out_dir)")
    return out_dir
end
