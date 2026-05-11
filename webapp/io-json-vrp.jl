using JSON3

const BENCHMARK_NAMES = Set(["Sintef2008", "Dimacs2021", "Mamut2026"])
const INSTANCE_ORIGINS = Set(["Solomon1987", "GehHom1999", "OsmCvrpGen"])
const PROBLEM_TYPES = Set(["CVRP", "VRPTW"])
const METRIC_VARIANTS = Set(["fastest", "shortest", "euclidean"])
const OBJECTIVE_FUNCTIONS = Set(["HierarchicalVehicleCost", "MonoCost"])
const FAMILY_CHANGE_KINDS = Set(["added", "removed"])
const INSTANCE_CHANGE_KINDS = Set(["added", "removed"])
const BKS_CHANGE_KINDS = Set(["added", "removed", "improved", "regressed"])
const SITE_PAYLOAD_KINDS = Set([
    "home_page",
    "site_snapshot",
    "site_history",
    "history_detail",
    "project_page",
    "benchmarks_index",
    "problem_index",
    "family_index",
    "variant_index",
    "place_index",
    "size_index",
    "instance_page",
    "objectives_page",
])
const CATALOG_PAYLOAD_KINDS = Set(["family_index", "variant_index", "place_index", "size_index"])
const VRP_TYPES = Set(["CVRP", "CVRPTW"])
const INTEGER_TOLERANCE = 1.0e-9
const KNOWN_VRP_SECTIONS = Set([
    "EDGE_WEIGHT_SECTION",
    "NODE_COORD_SECTION",
    "DEMAND_SECTION",
    "TIME_WINDOW_SECTION",
    "SERVICE_TIME_SECTION",
    "DEPOT_SECTION",
])


struct ArtifactPaths
    vrp_json::String
    vrp::String
    meta::String
    manifest::String
end


struct InstanceMetadata
    authors::String
    generated_at::String
    problem_type::String
    metric_variant::String
    place_slug::String
    source_base_name::String
    source_city::String
    source_seed::Int
    source_folder::String
    num_vehicles_lb::Union{Nothing,Int}
    submodule_git_commit::Union{Nothing,String}
    generator_version::Union{Nothing,String}
    artifact_paths::ArtifactPaths
    sibling_variant_paths::Dict{String,String}
    derived_problem_paths::Dict{String,String}
    source_problem_paths::Dict{String,String}
end


struct HistoricalBenchmarkInstance{T<:Real}
    instance_name::String
    instance_origin::String
    benchmark_name::String
    num_customers::Int
    num_vehicles::Union{Nothing,Int}
    vehicle_capacity::Int
    coordinates::Vector{NTuple{2,Float64}}
    demands::Vector{Int}
    service_times::Vector{Int}
    time_windows::Vector{NTuple{2,Int}}
    depot::Int
    arc_costs::Vector{Vector{T}}
end


const BenchmarkInstance = HistoricalBenchmarkInstance


struct BenchmarkInstanceCVRP{T<:Real}
    instance_id::String
    instance_origin::String
    benchmark_name::String
    num_customers::Int
    num_vehicles::Union{Nothing,Int}
    vehicle_capacity::Int
    coordinates::Vector{NTuple{2,Float64}}
    demands::Vector{Int}
    depot::Int
    arc_costs::Vector{Vector{T}}
    metadata::InstanceMetadata
end


struct BenchmarkInstanceVRPTW{T<:Real}
    instance_id::String
    instance_origin::String
    benchmark_name::String
    num_customers::Int
    num_vehicles::Union{Nothing,Int}
    vehicle_capacity::Int
    coordinates::Vector{NTuple{2,Float64}}
    demands::Vector{Int}
    service_times::Vector{Int}
    time_windows::Vector{NTuple{2,Int}}
    depot::Int
    arc_costs::Vector{Vector{T}}
    metadata::InstanceMetadata
end


struct BenchmarkBKS
    instance_name::String
    objective_function::String
    routes::Vector{Vector{Int}}
    cost::Union{Nothing,Int,Float64}
    metadata::Dict{String,Any}
end


struct SnapshotRef
    snapshot_id::String
    published_at::String
    source_commit::String
    source_branch::Union{Nothing,String}
end


struct SiteCounts
    problem_count::Int
    family_count::Int
    variant_count::Int
    place_count::Int
    size_bucket_count::Int
    instance_count::Int
    bks_count::Int
end


struct ObjectiveAvailability
    objective_function::String
    cost::Union{Nothing,Int,Float64}
    num_routes::Union{Nothing,Int}
    artifact_path::String
end


struct BreadcrumbItem
    label::String
    route_path::String
end


struct FilterOption
    value::String
    label::String
    count::Int
end


struct FilterFacet
    key::String
    label::String
    options::Vector{FilterOption}
end


struct BenchmarkLocator
    problem_type::String
    benchmark_name::String
    metric_variant::Union{Nothing,String}
    place_slug::Union{Nothing,String}
    size_bucket::String
    instance_identifier::String
end


struct ProblemSummaryCard
    problem_type::String
    route_path::String
    benchmark_names::Vector{String}
    family_count::Int
    instance_count::Int
    bks_count::Int
    supported_objective_functions::Vector{String}
end


struct FamilySummaryCard
    benchmark_name::String
    route_path::String
    metric_variants::Vector{String}
    instance_count::Int
    bks_count::Int
    supported_objective_functions::Vector{String}
end


struct SubrouteEntry
    key::String
    label::String
    route_path::String
    instance_count::Int
    bks_count::Int
end


struct ObjectiveExplainer
    objective_function::String
    short_label::String
    title::String
    description::String
    interpretation_notes::Vector{String}
    related_routes::Vector{SubrouteEntry}
end


struct CatalogSummary
    instance_count::Int
    bks_count::Int
    place_count::Int
    size_bucket_count::Int
    supported_objective_functions::Vector{String}
end


struct InstanceListItem
    locator::BenchmarkLocator
    display_name::String
    instance_id::String
    num_customers::Int
    route_path::String
    artifact_vrp_json_path::String
    place_slug::Union{Nothing,String}
    historical_topology_type::Union{Nothing,String}
    historical_tw_type::Union{Nothing,String}
    bks_count::Int
    viewer_render_mode::String
    road_cache_status::String
    objective_availability::Vector{ObjectiveAvailability}
end


struct SiteArtifactLinks
    vrp_json_path::String
    vrp_path::Union{Nothing,String}
    meta_path::Union{Nothing,String}
    manifest_path::Union{Nothing,String}
end


struct BKSPageEntry
    objective_function::String
    artifact_path::String
    num_routes::Int
    cost::Union{Nothing,Int,Float64}
    authors::Union{Nothing,String}
    source::Union{Nothing,String}
    method::Union{Nothing,String}
    validated_num_routes::Union{Nothing,Int}
end


struct InstancePageSummary
    display_name::String
    problem_type::String
    benchmark_name::String
    metric_variant::Union{Nothing,String}
    place_slug::Union{Nothing,String}
    size_bucket::String
    num_customers::Int
    historical_topology_type::Union{Nothing,String}
    historical_tw_type::Union{Nothing,String}
    num_vehicles::Union{Nothing,Int}
    num_vehicles_lb::Union{Nothing,Int}
    vehicle_capacity::Int
    authors::Union{Nothing,String}
    generated_at::Union{Nothing,String}
    source_city::Union{Nothing,String}
    has_geometry_sidecar::Bool
    viewer_render_mode::String
    road_cache_status::String
    road_cache_metrics::Vector{String}
    road_cache_entry_count::Int
    road_cache_expected_entry_count::Union{Nothing,Int}
    supported_objective_functions::Vector{String}
end


struct SiteSnapshotManifest
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    summary::String
    counts::SiteCounts
    benchmark_index_path::String
    history_path::String
    history_detail_path::String
end


struct BksValue
    cost::Union{Nothing,Int,Float64}
    num_routes::Union{Nothing,Int}
    authors::Union{Nothing,String}
    method::Union{Nothing,String}
end


struct FamilyChange
    problem_type::String
    benchmark_name::String
    kind::String
end


struct InstanceChange
    instance_id::String
    problem_type::String
    benchmark_name::String
    metric_variant::Union{Nothing,String}
    place_slug::Union{Nothing,String}
    num_customers::Int
    instance_name::String
    kind::String
end


struct BksChange
    instance_id::String
    problem_type::String
    benchmark_name::String
    metric_variant::Union{Nothing,String}
    place_slug::Union{Nothing,String}
    num_customers::Int
    instance_name::String
    objective_function::String
    kind::String
    prev::Union{Nothing,BksValue}
    new::Union{Nothing,BksValue}
    cost_delta::Union{Nothing,Int,Float64}
    cost_pct::Union{Nothing,Float64}
    routes_delta::Union{Nothing,Int}
    routes_pct::Union{Nothing,Float64}
end


struct ChangeCounts
    families_added::Int
    families_removed::Int
    instances_added::Int
    instances_removed::Int
    bks_added::Int
    bks_removed::Int
    bks_improved::Int
    bks_regressed::Int
end


struct SnapshotChangeLog
    is_initial::Bool
    counts::ChangeCounts
    family_changes::Vector{FamilyChange}
    instance_changes::Vector{InstanceChange}
    bks_changes::Vector{BksChange}
end


struct SiteHistoryEntry
    snapshot::SnapshotRef
    summary::String
    detail_route_path::String
    affected_problem_types::Vector{String}
    affected_benchmark_names::Vector{String}
    affected_objective_functions::Vector{String}
    change_counts::ChangeCounts
end


struct SiteHistoryLedger
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    current_snapshot_id::String
    entries::Vector{SiteHistoryEntry}
end


struct HomePagePayload
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    route_path::String
    title::String
    subtitle::String
    hero_summary::String
    latest_publication_summary::String
    counts::SiteCounts
    problems::Vector{ProblemSummaryCard}
    benchmarks_route_path::String
    project_route_path::String
    objectives_route_path::String
    history_route_path::String
    workbench_route_path::String
end


struct ProjectFact
    label::String
    value::String
    href::Union{Nothing,String}
end


struct ProjectNarrativeBlock
    title::String
    body::String
    tags::Vector{String}
end


struct ProjectPagePayload
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    route_path::String
    title::String
    subtitle::String
    breadcrumbs::Vector{BreadcrumbItem}
    anr_project_code::String
    anr_project_url::String
    anr_project_title::String
    anr_context::String
    facts::Vector{ProjectFact}
    research_threads::Vector{ProjectNarrativeBlock}
    collaboration_note::String
end


struct HistoryDetailPayload
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    route_path::String
    title::String
    breadcrumbs::Vector{BreadcrumbItem}
    summary::String
    counts::SiteCounts
    benchmark_index_path::String
    history_path::String
    affected_problem_types::Vector{String}
    affected_benchmark_names::Vector{String}
    affected_objective_functions::Vector{String}
    change_log::SnapshotChangeLog
end


struct BenchmarksIndexPayload
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    route_path::String
    breadcrumbs::Vector{BreadcrumbItem}
    problems::Vector{ProblemSummaryCard}
end


struct ProblemIndexPayload
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    route_path::String
    title::String
    breadcrumbs::Vector{BreadcrumbItem}
    problem_type::String
    summary::CatalogSummary
    families::Vector{FamilySummaryCard}
end


struct CatalogIndexPayload
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    route_path::String
    title::String
    description::Union{Nothing,String}
    breadcrumbs::Vector{BreadcrumbItem}
    problem_type::String
    benchmark_name::String
    metric_variant::Union{Nothing,String}
    place_slug::Union{Nothing,String}
    size_bucket::Union{Nothing,String}
    summary::CatalogSummary
    filter_facets::Vector{FilterFacet}
    variant_routes::Vector{SubrouteEntry}
    place_routes::Vector{SubrouteEntry}
    size_routes::Vector{SubrouteEntry}
    items::Vector{InstanceListItem}
end


struct InstancePagePayload
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    route_path::String
    title::String
    breadcrumbs::Vector{BreadcrumbItem}
    locator::BenchmarkLocator
    summary::InstancePageSummary
    artifact_links::SiteArtifactLinks
    sibling_variant_routes::Dict{String,String}
    derived_problem_routes::Dict{String,String}
    source_problem_routes::Dict{String,String}
    bks_entries::Vector{BKSPageEntry}
    workbench_route_path::String
end


struct ObjectivesPagePayload
    payload_kind::String
    schema_version::String
    generated_at::String
    snapshot::SnapshotRef
    route_path::String
    title::String
    breadcrumbs::Vector{BreadcrumbItem}
    explainers::Vector{ObjectiveExplainer}
end


struct ParsedVrpInstance{T<:Real}
    name::String
    vrp_type::String
    comment::Union{Nothing,String}
    dimension::Int
    capacity::Int
    arc_costs::Vector{Vector{T}}
    coordinates::Vector{NTuple{2,Float64}}
    demands::Vector{Int}
    depot::Int
    service_times::Union{Nothing,Vector{Int}}
    time_windows::Union{Nothing,Vector{NTuple{2,Int}}}
end


is_integral_number(value) = value isa Integer

function is_integral_number(value::AbstractFloat)
    return isfinite(value) && abs(value - round(value)) <= INTEGER_TOLERANCE
end


function indent_prefix(level::Int, indent::Int)
    return repeat(" ", indent * level)
end


function json_scalar_string(value)
    return sprint(io -> JSON3.write(io, value))
end


function ensure_allowed_keys(payload::AbstractDict, allowed_keys::Set{String}, type_name::AbstractString)
    for key in keys(payload)
        key_string = String(key)
        key_string in allowed_keys || error("$type_name received unexpected field '$key_string'")
    end
    return payload
end


function require_field(payload::AbstractDict, field_name::AbstractString)
    haskey(payload, field_name) || error("Missing required field '$field_name'")
    return payload[field_name]
end


function require_choice(value::AbstractString, allowed::Set{String}, field_name::AbstractString)
    string_value = String(value)
    string_value in allowed || error("$field_name must be one of $(collect(allowed))")
    return string_value
end


function validate_relative_path(path_value::AbstractString)
    startswith(path_value, "/") && error("paths must be relative to the MAMUT-routing repository root")
    isempty(path_value) && error("paths must be non-empty")
    return String(path_value)
end


function coerce_string(value, field_name::AbstractString)
    value isa AbstractString || error("$field_name must be a string")
    return String(value)
end


function coerce_optional_string(value, field_name::AbstractString)
    value === nothing && return nothing
    return coerce_string(value, field_name)
end


function validate_site_path(path_value::AbstractString, field_name::AbstractString)
    isempty(path_value) && error("$field_name must be non-empty")
    startswith(path_value, "/") || error("$field_name must be rooted at the website path prefix")
    return String(path_value)
end


function coerce_int(value, field_name::AbstractString)
    value isa Bool && error("$field_name must be numeric, not Bool")
    value isa Integer && return Int(value)
    value isa AbstractFloat && is_integral_number(value) && return round(Int, value)
    error("$field_name must be an integer-compatible numeric value")
end


function coerce_optional_int(value, field_name::AbstractString)
    value === nothing && return nothing
    return coerce_int(value, field_name)
end


function coerce_real(value, field_name::AbstractString)
    value isa Bool && error("$field_name must be numeric, not Bool")
    value isa Real || error("$field_name must contain only numeric values")
    return Float64(value)
end


function coerce_cost(value, field_name::AbstractString)
    value === nothing && return nothing
    value isa Bool && error("$field_name must be numeric, not Bool")
    value isa Integer && return Int(value)
    value isa Real && return Float64(value)
    error("$field_name must be numeric")
end


function normalize_choice_vector(values, allowed::Set{String}, field_name::AbstractString)
    values isa AbstractVector || error("$field_name must be a list")
    return [require_choice(coerce_string(value, field_name), allowed, field_name) for value in values]
end


function normalize_string_vector(values, field_name::AbstractString)
    values isa AbstractVector || error("$field_name must be a list")
    return [coerce_string(value, field_name) for value in values]
end


function normalize_object_vector(values, field_name::AbstractString, parser)
    values isa AbstractVector || error("$field_name must be a list")
    return [parser(value isa AbstractDict ? value : error("Each element in $field_name must be an object")) for value in values]
end


function require_positive(value::Int, field_name::AbstractString)
    value > 0 || error("$field_name must be positive")
    return value
end


function require_nonnegative(value::Int, field_name::AbstractString)
    value >= 0 || error("$field_name must be non-negative")
    return value
end


function normalize_coordinate_vector(values, field_name::AbstractString)
    coordinates = NTuple{2,Float64}[]
    for (index, value) in enumerate(values)
        value isa AbstractVector || value isa Tuple || error("Each element in $field_name must be a 2-vector (at index $index)")
        length(value) == 2 || error("Each element in $field_name must have length 2 (at index $index)")
        push!(coordinates, (coerce_real(value[1], field_name), coerce_real(value[2], field_name)))
    end
    return coordinates
end


function normalize_pair_int_vector(values, field_name::AbstractString)
    pairs_vector = NTuple{2,Int}[]
    for (index, value) in enumerate(values)
        value isa AbstractVector || value isa Tuple || error("Each element in $field_name must be a 2-vector (at index $index)")
        length(value) == 2 || error("Each element in $field_name must have length 2 (at index $index)")
        push!(pairs_vector, (coerce_int(value[1], field_name), coerce_int(value[2], field_name)))
    end
    return pairs_vector
end


function normalize_int_vector(values, field_name::AbstractString)
    return [coerce_int(value, field_name) for value in values]
end


function normalize_string_map(values, field_name::AbstractString; relative_paths::Bool=false)
    values isa AbstractDict || error("$field_name must be an object")
    result = Dict{String,String}()
    for (key, value) in pairs(values)
        key_string = coerce_string(key, "$field_name key")
        value_string = coerce_string(value, field_name)
        result[key_string] = relative_paths ? validate_relative_path(value_string) : value_string
    end
    return result
end


function normalize_any_dict(values, field_name::AbstractString)
    values isa AbstractDict || error("$field_name must be an object")
    return Dict{String,Any}(String(key) => value for (key, value) in pairs(values))
end


function normalize_routes(values)
    values isa AbstractVector || error("routes must be a list of routes")
    routes = Vector{Vector{Int}}()
    for (route_index, route) in enumerate(values)
        route isa AbstractVector || error("Route $route_index must be a list")
        push!(routes, [coerce_int(value, "routes") for value in route])
    end
    return routes
end


function normalize_arc_costs(values)
    values isa AbstractVector || error("arc_costs must be a matrix")
    rows = [collect(row) for row in values]
    isempty(rows) && error("arc_costs must not be empty")

    expected_width = length(rows[1])
    for row in rows
        length(row) == expected_width || error("Each row in arc_costs must have the same number of columns")
        for value in row
            value isa Bool && error("arc_costs must contain only numeric values")
            value isa Real || error("arc_costs must contain only numeric values")
        end
    end

    if all(is_integral_number, Iterators.flatten(rows))
        return [[coerce_int(value, "arc_costs") for value in row] for row in rows]
    end

    return [[coerce_real(value, "arc_costs") for value in row] for row in rows]
end


function validate_instance_vectors(
    num_customers::Int,
    coordinates::Vector{NTuple{2,Float64}},
    demands::Vector{Int},
    depot::Int,
    arc_costs,
)
    expected_length = num_customers + 1
    length(coordinates) == expected_length || error("Length of coordinates must be $expected_length (based on num_customers=$num_customers + 1 for depot)")
    length(demands) == expected_length || error("Length of demands must be $expected_length (based on num_customers=$num_customers + 1 for depot)")
    length(arc_costs) == expected_length || error("arc_costs must have $expected_length rows (based on num_customers=$num_customers + 1 for depot)")
    all(length(row) == expected_length for row in arc_costs) || error("Each row in arc_costs must have $expected_length columns (based on num_customers=$num_customers + 1 for depot)")
    0 <= depot < expected_length || error("depot must be in [0, $(expected_length - 1)]")
    return expected_length
end


function validate_vrptw_vectors(num_customers::Int, service_times::Vector{Int}, time_windows::Vector{NTuple{2,Int}})
    expected_length = num_customers + 1
    length(service_times) == expected_length || error("Length of service_times must be $expected_length (based on num_customers=$num_customers + 1 for depot)")
    length(time_windows) == expected_length || error("Length of time_windows must be $expected_length (based on num_customers=$num_customers + 1 for depot)")
    return expected_length
end


function ArtifactPaths(; vrp_json, vrp, meta, manifest)
    return ArtifactPaths(
        validate_relative_path(coerce_string(vrp_json, "vrp_json")),
        validate_relative_path(coerce_string(vrp, "vrp")),
        validate_relative_path(coerce_string(meta, "meta")),
        validate_relative_path(coerce_string(manifest, "manifest")),
    )
end


function InstanceMetadata(;
    authors,
    generated_at,
    problem_type,
    metric_variant,
    place_slug,
    source_base_name,
    source_city,
    source_seed,
    source_folder,
    num_vehicles_lb=nothing,
    submodule_git_commit=nothing,
    generator_version=nothing,
    artifact_paths,
    sibling_variant_paths=Dict{String,String}(),
    derived_problem_paths=Dict{String,String}(),
    source_problem_paths=Dict{String,String}(),
)
    num_vehicles_lb_int = coerce_optional_int(num_vehicles_lb, "num_vehicles_lb")
    num_vehicles_lb_int === nothing || require_positive(num_vehicles_lb_int, "num_vehicles_lb")

    artifact_paths_value = artifact_paths isa ArtifactPaths ? artifact_paths : artifact_paths_from_dict(artifact_paths)
    sibling_paths = normalize_string_map(sibling_variant_paths, "sibling_variant_paths"; relative_paths=true)
    derived_paths = normalize_string_map(derived_problem_paths, "derived_problem_paths"; relative_paths=true)
    source_paths = normalize_string_map(source_problem_paths, "source_problem_paths"; relative_paths=true)

    return InstanceMetadata(
        coerce_string(authors, "authors"),
        coerce_string(generated_at, "generated_at"),
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        require_choice(coerce_string(metric_variant, "metric_variant"), METRIC_VARIANTS, "metric_variant"),
        coerce_string(place_slug, "place_slug"),
        coerce_string(source_base_name, "source_base_name"),
        coerce_string(source_city, "source_city"),
        coerce_int(source_seed, "source_seed"),
        coerce_string(source_folder, "source_folder"),
        num_vehicles_lb_int,
        coerce_optional_string(submodule_git_commit, "submodule_git_commit"),
        coerce_optional_string(generator_version, "generator_version"),
        artifact_paths_value,
        sibling_paths,
        derived_paths,
        source_paths,
    )
end


function HistoricalBenchmarkInstance(;
    instance_name,
    instance_origin,
    benchmark_name,
    num_customers,
    num_vehicles=nothing,
    vehicle_capacity,
    coordinates,
    demands,
    service_times,
    time_windows,
    depot=0,
    arc_costs,
)
    num_customers_int = require_positive(coerce_int(num_customers, "num_customers"), "num_customers")
    num_vehicles_int = coerce_optional_int(num_vehicles, "num_vehicles")
    num_vehicles_int === nothing || require_positive(num_vehicles_int, "num_vehicles")
    vehicle_capacity_int = require_positive(coerce_int(vehicle_capacity, "vehicle_capacity"), "vehicle_capacity")
    coordinates_vec = normalize_coordinate_vector(coordinates, "coordinates")
    demands_vec = normalize_int_vector(demands, "demands")
    service_times_vec = normalize_int_vector(service_times, "service_times")
    time_windows_vec = normalize_pair_int_vector(time_windows, "time_windows")
    depot_int = require_nonnegative(coerce_int(depot, "depot"), "depot")
    arc_costs_matrix = normalize_arc_costs(arc_costs)

    validate_instance_vectors(num_customers_int, coordinates_vec, demands_vec, depot_int, arc_costs_matrix)
    validate_vrptw_vectors(num_customers_int, service_times_vec, time_windows_vec)
    benchmark_name_str = require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name")
    instance_origin_str = require_choice(coerce_string(instance_origin, "instance_origin"), INSTANCE_ORIGINS, "instance_origin")
    matrix_type = eltype(first(arc_costs_matrix))

    return HistoricalBenchmarkInstance{matrix_type}(
        coerce_string(instance_name, "instance_name"),
        instance_origin_str,
        benchmark_name_str,
        num_customers_int,
        num_vehicles_int,
        vehicle_capacity_int,
        coordinates_vec,
        demands_vec,
        service_times_vec,
        time_windows_vec,
        depot_int,
        arc_costs_matrix,
    )
end


function BenchmarkInstanceCVRP(;
    instance_id,
    instance_origin,
    benchmark_name,
    num_customers,
    num_vehicles=nothing,
    vehicle_capacity,
    coordinates,
    demands,
    depot=0,
    arc_costs,
    metadata,
)
    num_customers_int = require_positive(coerce_int(num_customers, "num_customers"), "num_customers")
    num_vehicles_int = coerce_optional_int(num_vehicles, "num_vehicles")
    num_vehicles_int === nothing || require_positive(num_vehicles_int, "num_vehicles")
    vehicle_capacity_int = require_positive(coerce_int(vehicle_capacity, "vehicle_capacity"), "vehicle_capacity")
    coordinates_vec = normalize_coordinate_vector(coordinates, "coordinates")
    demands_vec = normalize_int_vector(demands, "demands")
    depot_int = require_nonnegative(coerce_int(depot, "depot"), "depot")
    arc_costs_matrix = normalize_arc_costs(arc_costs)
    metadata_value = metadata isa InstanceMetadata ? metadata : instance_metadata_from_dict(metadata)

    validate_instance_vectors(num_customers_int, coordinates_vec, demands_vec, depot_int, arc_costs_matrix)
    benchmark_name_str = require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name")
    instance_origin_str = require_choice(coerce_string(instance_origin, "instance_origin"), INSTANCE_ORIGINS, "instance_origin")
    matrix_type = eltype(first(arc_costs_matrix))

    return BenchmarkInstanceCVRP{matrix_type}(
        coerce_string(instance_id, "instance_id"),
        instance_origin_str,
        benchmark_name_str,
        num_customers_int,
        num_vehicles_int,
        vehicle_capacity_int,
        coordinates_vec,
        demands_vec,
        depot_int,
        arc_costs_matrix,
        metadata_value,
    )
end


function BenchmarkInstanceVRPTW(;
    instance_id,
    instance_origin,
    benchmark_name,
    num_customers,
    num_vehicles=nothing,
    vehicle_capacity,
    coordinates,
    demands,
    service_times,
    time_windows,
    depot=0,
    arc_costs,
    metadata,
)
    num_customers_int = require_positive(coerce_int(num_customers, "num_customers"), "num_customers")
    num_vehicles_int = coerce_optional_int(num_vehicles, "num_vehicles")
    num_vehicles_int === nothing || require_positive(num_vehicles_int, "num_vehicles")
    vehicle_capacity_int = require_positive(coerce_int(vehicle_capacity, "vehicle_capacity"), "vehicle_capacity")
    coordinates_vec = normalize_coordinate_vector(coordinates, "coordinates")
    demands_vec = normalize_int_vector(demands, "demands")
    service_times_vec = normalize_int_vector(service_times, "service_times")
    time_windows_vec = normalize_pair_int_vector(time_windows, "time_windows")
    depot_int = require_nonnegative(coerce_int(depot, "depot"), "depot")
    arc_costs_matrix = normalize_arc_costs(arc_costs)
    metadata_value = metadata isa InstanceMetadata ? metadata : instance_metadata_from_dict(metadata)

    validate_instance_vectors(num_customers_int, coordinates_vec, demands_vec, depot_int, arc_costs_matrix)
    validate_vrptw_vectors(num_customers_int, service_times_vec, time_windows_vec)
    benchmark_name_str = require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name")
    instance_origin_str = require_choice(coerce_string(instance_origin, "instance_origin"), INSTANCE_ORIGINS, "instance_origin")
    matrix_type = eltype(first(arc_costs_matrix))

    return BenchmarkInstanceVRPTW{matrix_type}(
        coerce_string(instance_id, "instance_id"),
        instance_origin_str,
        benchmark_name_str,
        num_customers_int,
        num_vehicles_int,
        vehicle_capacity_int,
        coordinates_vec,
        demands_vec,
        service_times_vec,
        time_windows_vec,
        depot_int,
        arc_costs_matrix,
        metadata_value,
    )
end


function BenchmarkBKS(; instance_name, objective_function, routes, cost=nothing, metadata=Dict{String,Any}())
    metadata_value = normalize_any_dict(metadata, "metadata")
    return BenchmarkBKS(
        coerce_string(instance_name, "instance_name"),
        require_choice(coerce_string(objective_function, "objective_function"), OBJECTIVE_FUNCTIONS, "objective_function"),
        normalize_routes(routes),
        coerce_cost(cost, "cost"),
        metadata_value,
    )
end


function SnapshotRef(; snapshot_id, published_at, source_commit, source_branch=nothing)
    return SnapshotRef(
        coerce_string(snapshot_id, "snapshot_id"),
        coerce_string(published_at, "published_at"),
        coerce_string(source_commit, "source_commit"),
        coerce_optional_string(source_branch, "source_branch"),
    )
end


function SiteCounts(; problem_count, family_count, variant_count, place_count, size_bucket_count, instance_count, bks_count)
    return SiteCounts(
        require_nonnegative(coerce_int(problem_count, "problem_count"), "problem_count"),
        require_nonnegative(coerce_int(family_count, "family_count"), "family_count"),
        require_nonnegative(coerce_int(variant_count, "variant_count"), "variant_count"),
        require_nonnegative(coerce_int(place_count, "place_count"), "place_count"),
        require_nonnegative(coerce_int(size_bucket_count, "size_bucket_count"), "size_bucket_count"),
        require_nonnegative(coerce_int(instance_count, "instance_count"), "instance_count"),
        require_nonnegative(coerce_int(bks_count, "bks_count"), "bks_count"),
    )
end


function ObjectiveAvailability(; objective_function, cost=nothing, num_routes=nothing, artifact_path)
    num_routes_int = coerce_optional_int(num_routes, "num_routes")
    num_routes_int === nothing || require_nonnegative(num_routes_int, "num_routes")
    return ObjectiveAvailability(
        require_choice(coerce_string(objective_function, "objective_function"), OBJECTIVE_FUNCTIONS, "objective_function"),
        coerce_cost(cost, "cost"),
        num_routes_int,
        coerce_string(artifact_path, "artifact_path"),
    )
end


function BreadcrumbItem(; label, route_path)
    return BreadcrumbItem(
        coerce_string(label, "label"),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
    )
end


function FilterOption(; value, label, count)
    return FilterOption(
        coerce_string(value, "value"),
        coerce_string(label, "label"),
        require_nonnegative(coerce_int(count, "count"), "count"),
    )
end


function FilterFacet(; key, label, options)
    return FilterFacet(
        coerce_string(key, "key"),
        coerce_string(label, "label"),
        options isa AbstractVector ? [option isa FilterOption ? option : filter_option_from_dict(option) for option in options] : error("options must be a list"),
    )
end


function BenchmarkLocator(; problem_type, benchmark_name, metric_variant=nothing, place_slug=nothing, size_bucket, instance_identifier)
    metric_variant_value = coerce_optional_string(metric_variant, "metric_variant")
    metric_variant_value === nothing || require_choice(metric_variant_value, METRIC_VARIANTS, "metric_variant")
    return BenchmarkLocator(
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name"),
        metric_variant_value,
        coerce_optional_string(place_slug, "place_slug"),
        coerce_string(size_bucket, "size_bucket"),
        coerce_string(instance_identifier, "instance_identifier"),
    )
end


function ProblemSummaryCard(; problem_type, route_path, benchmark_names, family_count, instance_count, bks_count, supported_objective_functions)
    return ProblemSummaryCard(
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        normalize_choice_vector(benchmark_names, BENCHMARK_NAMES, "benchmark_names"),
        require_nonnegative(coerce_int(family_count, "family_count"), "family_count"),
        require_nonnegative(coerce_int(instance_count, "instance_count"), "instance_count"),
        require_nonnegative(coerce_int(bks_count, "bks_count"), "bks_count"),
        normalize_choice_vector(supported_objective_functions, OBJECTIVE_FUNCTIONS, "supported_objective_functions"),
    )
end


function FamilySummaryCard(; benchmark_name, route_path, metric_variants, instance_count, bks_count, supported_objective_functions)
    return FamilySummaryCard(
        require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name"),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        normalize_choice_vector(metric_variants, METRIC_VARIANTS, "metric_variants"),
        require_nonnegative(coerce_int(instance_count, "instance_count"), "instance_count"),
        require_nonnegative(coerce_int(bks_count, "bks_count"), "bks_count"),
        normalize_choice_vector(supported_objective_functions, OBJECTIVE_FUNCTIONS, "supported_objective_functions"),
    )
end


function SubrouteEntry(; key, label, route_path, instance_count, bks_count)
    return SubrouteEntry(
        coerce_string(key, "key"),
        coerce_string(label, "label"),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        require_nonnegative(coerce_int(instance_count, "instance_count"), "instance_count"),
        require_nonnegative(coerce_int(bks_count, "bks_count"), "bks_count"),
    )
end


function ObjectiveExplainer(; objective_function, short_label, title, description, interpretation_notes, related_routes=SubrouteEntry[])
    return ObjectiveExplainer(
        require_choice(coerce_string(objective_function, "objective_function"), OBJECTIVE_FUNCTIONS, "objective_function"),
        coerce_string(short_label, "short_label"),
        coerce_string(title, "title"),
        coerce_string(description, "description"),
        normalize_string_vector(interpretation_notes, "interpretation_notes"),
        related_routes isa AbstractVector ? [route isa SubrouteEntry ? route : subroute_entry_from_dict(route) for route in related_routes] : error("related_routes must be a list"),
    )
end


function CatalogSummary(; instance_count, bks_count, place_count, size_bucket_count, supported_objective_functions)
    return CatalogSummary(
        require_nonnegative(coerce_int(instance_count, "instance_count"), "instance_count"),
        require_nonnegative(coerce_int(bks_count, "bks_count"), "bks_count"),
        require_nonnegative(coerce_int(place_count, "place_count"), "place_count"),
        require_nonnegative(coerce_int(size_bucket_count, "size_bucket_count"), "size_bucket_count"),
        normalize_choice_vector(supported_objective_functions, OBJECTIVE_FUNCTIONS, "supported_objective_functions"),
    )
end


function InstanceListItem(; locator, display_name, instance_id, num_customers, route_path, artifact_vrp_json_path, place_slug=nothing, historical_topology_type=nothing, historical_tw_type=nothing, bks_count, viewer_render_mode="straight_line", road_cache_status="not_applicable", objective_availability)
    return InstanceListItem(
        locator isa BenchmarkLocator ? locator : benchmark_locator_from_dict(locator),
        coerce_string(display_name, "display_name"),
        coerce_string(instance_id, "instance_id"),
        require_nonnegative(coerce_int(num_customers, "num_customers"), "num_customers"),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        validate_relative_path(coerce_string(artifact_vrp_json_path, "artifact_vrp_json_path")),
        coerce_optional_string(place_slug, "place_slug"),
        coerce_optional_string(historical_topology_type, "historical_topology_type"),
        coerce_optional_string(historical_tw_type, "historical_tw_type"),
        require_nonnegative(coerce_int(bks_count, "bks_count"), "bks_count"),
        coerce_string(viewer_render_mode, "viewer_render_mode"),
        coerce_string(road_cache_status, "road_cache_status"),
        objective_availability isa AbstractVector ? [entry isa ObjectiveAvailability ? entry : objective_availability_from_dict(entry) for entry in objective_availability] : error("objective_availability must be a list"),
    )
end


function SiteArtifactLinks(; vrp_json_path, vrp_path=nothing, meta_path=nothing, manifest_path=nothing)
    return SiteArtifactLinks(
        validate_relative_path(coerce_string(vrp_json_path, "vrp_json_path")),
        vrp_path === nothing ? nothing : validate_relative_path(coerce_string(vrp_path, "vrp_path")),
        meta_path === nothing ? nothing : validate_relative_path(coerce_string(meta_path, "meta_path")),
        manifest_path === nothing ? nothing : validate_relative_path(coerce_string(manifest_path, "manifest_path")),
    )
end


function BKSPageEntry(; objective_function, artifact_path, num_routes, cost=nothing, authors=nothing, source=nothing, method=nothing, validated_num_routes=nothing)
    validated_num_routes_int = coerce_optional_int(validated_num_routes, "validated_num_routes")
    validated_num_routes_int === nothing || require_nonnegative(validated_num_routes_int, "validated_num_routes")
    return BKSPageEntry(
        require_choice(coerce_string(objective_function, "objective_function"), OBJECTIVE_FUNCTIONS, "objective_function"),
        validate_relative_path(coerce_string(artifact_path, "artifact_path")),
        require_nonnegative(coerce_int(num_routes, "num_routes"), "num_routes"),
        coerce_cost(cost, "cost"),
        coerce_optional_string(authors, "authors"),
        coerce_optional_string(source, "source"),
        coerce_optional_string(method, "method"),
        validated_num_routes_int,
    )
end


function InstancePageSummary(; display_name, problem_type, benchmark_name, metric_variant=nothing, place_slug=nothing, size_bucket, num_customers, historical_topology_type=nothing, historical_tw_type=nothing, num_vehicles=nothing, num_vehicles_lb=nothing, vehicle_capacity, authors=nothing, generated_at=nothing, source_city=nothing, has_geometry_sidecar=false, viewer_render_mode="straight_line", road_cache_status="not_applicable", road_cache_metrics=String[], road_cache_entry_count=0, road_cache_expected_entry_count=nothing, supported_objective_functions)
    metric_variant_value = coerce_optional_string(metric_variant, "metric_variant")
    metric_variant_value === nothing || require_choice(metric_variant_value, METRIC_VARIANTS, "metric_variant")
    num_vehicles_int = coerce_optional_int(num_vehicles, "num_vehicles")
    num_vehicles_lb_int = coerce_optional_int(num_vehicles_lb, "num_vehicles_lb")
    road_cache_entry_count_int = require_nonnegative(coerce_int(road_cache_entry_count, "road_cache_entry_count"), "road_cache_entry_count")
    road_cache_expected_entry_count_int = coerce_optional_int(road_cache_expected_entry_count, "road_cache_expected_entry_count")
    num_vehicles_int === nothing || require_nonnegative(num_vehicles_int, "num_vehicles")
    num_vehicles_lb_int === nothing || require_nonnegative(num_vehicles_lb_int, "num_vehicles_lb")
    road_cache_expected_entry_count_int === nothing || require_nonnegative(road_cache_expected_entry_count_int, "road_cache_expected_entry_count")
    return InstancePageSummary(
        coerce_string(display_name, "display_name"),
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name"),
        metric_variant_value,
        coerce_optional_string(place_slug, "place_slug"),
        coerce_string(size_bucket, "size_bucket"),
        require_positive(coerce_int(num_customers, "num_customers"), "num_customers"),
        coerce_optional_string(historical_topology_type, "historical_topology_type"),
        coerce_optional_string(historical_tw_type, "historical_tw_type"),
        num_vehicles_int,
        num_vehicles_lb_int,
        require_positive(coerce_int(vehicle_capacity, "vehicle_capacity"), "vehicle_capacity"),
        coerce_optional_string(authors, "authors"),
        coerce_optional_string(generated_at, "generated_at"),
        coerce_optional_string(source_city, "source_city"),
        has_geometry_sidecar isa Bool ? has_geometry_sidecar : error("has_geometry_sidecar must be a Bool"),
        coerce_string(viewer_render_mode, "viewer_render_mode"),
        coerce_string(road_cache_status, "road_cache_status"),
        road_cache_metrics isa AbstractVector ? [coerce_string(metric, "road_cache_metrics") for metric in road_cache_metrics] : error("road_cache_metrics must be a list"),
        road_cache_entry_count_int,
        road_cache_expected_entry_count_int,
        normalize_choice_vector(supported_objective_functions, OBJECTIVE_FUNCTIONS, "supported_objective_functions"),
    )
end


function SiteSnapshotManifest(; payload_kind, schema_version, generated_at, snapshot, summary, counts, benchmark_index_path, history_path, history_detail_path)
    return SiteSnapshotManifest(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        coerce_string(summary, "summary"),
        counts isa SiteCounts ? counts : site_counts_from_dict(counts),
        validate_site_path(coerce_string(benchmark_index_path, "benchmark_index_path"), "benchmark_index_path"),
        validate_site_path(coerce_string(history_path, "history_path"), "history_path"),
        validate_site_path(coerce_string(history_detail_path, "history_detail_path"), "history_detail_path"),
    )
end


function BksValue(; cost=nothing, num_routes=nothing, authors=nothing, method=nothing)
    num_routes_int = coerce_optional_int(num_routes, "num_routes")
    num_routes_int === nothing || require_nonnegative(num_routes_int, "num_routes")
    return BksValue(
        coerce_cost(cost, "cost"),
        num_routes_int,
        coerce_optional_string(authors, "authors"),
        coerce_optional_string(method, "method"),
    )
end


function FamilyChange(; problem_type, benchmark_name, kind)
    return FamilyChange(
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name"),
        require_choice(coerce_string(kind, "kind"), FAMILY_CHANGE_KINDS, "kind"),
    )
end


function InstanceChange(; instance_id, problem_type, benchmark_name, metric_variant=nothing, place_slug=nothing, num_customers, instance_name, kind)
    metric_variant_value = coerce_optional_string(metric_variant, "metric_variant")
    metric_variant_value === nothing || require_choice(metric_variant_value, METRIC_VARIANTS, "metric_variant")
    return InstanceChange(
        coerce_string(instance_id, "instance_id"),
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name"),
        metric_variant_value,
        coerce_optional_string(place_slug, "place_slug"),
        require_nonnegative(coerce_int(num_customers, "num_customers"), "num_customers"),
        coerce_string(instance_name, "instance_name"),
        require_choice(coerce_string(kind, "kind"), INSTANCE_CHANGE_KINDS, "kind"),
    )
end


function BksChange(; instance_id, problem_type, benchmark_name, metric_variant=nothing, place_slug=nothing, num_customers, instance_name, objective_function, kind, prev=nothing, new=nothing, cost_delta=nothing, cost_pct=nothing, routes_delta=nothing, routes_pct=nothing)
    metric_variant_value = coerce_optional_string(metric_variant, "metric_variant")
    metric_variant_value === nothing || require_choice(metric_variant_value, METRIC_VARIANTS, "metric_variant")
    routes_delta_int = coerce_optional_int(routes_delta, "routes_delta")
    return BksChange(
        coerce_string(instance_id, "instance_id"),
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name"),
        metric_variant_value,
        coerce_optional_string(place_slug, "place_slug"),
        require_nonnegative(coerce_int(num_customers, "num_customers"), "num_customers"),
        coerce_string(instance_name, "instance_name"),
        require_choice(coerce_string(objective_function, "objective_function"), OBJECTIVE_FUNCTIONS, "objective_function"),
        require_choice(coerce_string(kind, "kind"), BKS_CHANGE_KINDS, "kind"),
        prev === nothing ? nothing : (prev isa BksValue ? prev : bks_value_from_dict(prev)),
        new === nothing ? nothing : (new isa BksValue ? new : bks_value_from_dict(new)),
        coerce_cost(cost_delta, "cost_delta"),
        cost_pct === nothing ? nothing : Float64(cost_pct),
        routes_delta_int,
        routes_pct === nothing ? nothing : Float64(routes_pct),
    )
end


function ChangeCounts(; families_added=0, families_removed=0, instances_added=0, instances_removed=0, bks_added=0, bks_removed=0, bks_improved=0, bks_regressed=0)
    return ChangeCounts(
        require_nonnegative(coerce_int(families_added, "families_added"), "families_added"),
        require_nonnegative(coerce_int(families_removed, "families_removed"), "families_removed"),
        require_nonnegative(coerce_int(instances_added, "instances_added"), "instances_added"),
        require_nonnegative(coerce_int(instances_removed, "instances_removed"), "instances_removed"),
        require_nonnegative(coerce_int(bks_added, "bks_added"), "bks_added"),
        require_nonnegative(coerce_int(bks_removed, "bks_removed"), "bks_removed"),
        require_nonnegative(coerce_int(bks_improved, "bks_improved"), "bks_improved"),
        require_nonnegative(coerce_int(bks_regressed, "bks_regressed"), "bks_regressed"),
    )
end


function SnapshotChangeLog(; is_initial, counts, family_changes=Any[], instance_changes=Any[], bks_changes=Any[])
    return SnapshotChangeLog(
        Bool(is_initial),
        counts isa ChangeCounts ? counts : change_counts_from_dict(counts),
        family_changes isa AbstractVector ? [c isa FamilyChange ? c : family_change_from_dict(c) for c in family_changes] : error("family_changes must be a list"),
        instance_changes isa AbstractVector ? [c isa InstanceChange ? c : instance_change_from_dict(c) for c in instance_changes] : error("instance_changes must be a list"),
        bks_changes isa AbstractVector ? [c isa BksChange ? c : bks_change_from_dict(c) for c in bks_changes] : error("bks_changes must be a list"),
    )
end


function SiteHistoryEntry(; snapshot, summary, detail_route_path, affected_problem_types=String[], affected_benchmark_names=String[], affected_objective_functions=String[], change_counts=Dict{String,Any}())
    return SiteHistoryEntry(
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        coerce_string(summary, "summary"),
        validate_site_path(coerce_string(detail_route_path, "detail_route_path"), "detail_route_path"),
        normalize_choice_vector(affected_problem_types, PROBLEM_TYPES, "affected_problem_types"),
        normalize_choice_vector(affected_benchmark_names, BENCHMARK_NAMES, "affected_benchmark_names"),
        normalize_choice_vector(affected_objective_functions, OBJECTIVE_FUNCTIONS, "affected_objective_functions"),
        change_counts isa ChangeCounts ? change_counts : change_counts_from_dict(change_counts),
    )
end


function SiteHistoryLedger(; payload_kind, schema_version, generated_at, snapshot, current_snapshot_id, entries)
    return SiteHistoryLedger(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        coerce_string(current_snapshot_id, "current_snapshot_id"),
        entries isa AbstractVector ? [entry isa SiteHistoryEntry ? entry : site_history_entry_from_dict(entry) for entry in entries] : error("entries must be a list"),
    )
end


function HomePagePayload(; payload_kind, schema_version, generated_at, snapshot, route_path="/", title, subtitle, hero_summary, latest_publication_summary, counts, problems, benchmarks_route_path="/benchmarks/", project_route_path="/project/", objectives_route_path="/objectives/", history_route_path="/history/", workbench_route_path="/workbench/")
    return HomePagePayload(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        coerce_string(title, "title"),
        coerce_string(subtitle, "subtitle"),
        coerce_string(hero_summary, "hero_summary"),
        coerce_string(latest_publication_summary, "latest_publication_summary"),
        counts isa SiteCounts ? counts : site_counts_from_dict(counts),
        problems isa AbstractVector ? [problem isa ProblemSummaryCard ? problem : problem_summary_card_from_dict(problem) for problem in problems] : error("problems must be a list"),
        validate_site_path(coerce_string(benchmarks_route_path, "benchmarks_route_path"), "benchmarks_route_path"),
        validate_site_path(coerce_string(project_route_path, "project_route_path"), "project_route_path"),
        validate_site_path(coerce_string(objectives_route_path, "objectives_route_path"), "objectives_route_path"),
        validate_site_path(coerce_string(history_route_path, "history_route_path"), "history_route_path"),
        validate_site_path(coerce_string(workbench_route_path, "workbench_route_path"), "workbench_route_path"),
    )
end


function ProjectFact(; label, value, href=nothing)
    return ProjectFact(
        coerce_string(label, "label"),
        coerce_string(value, "value"),
        coerce_optional_string(href, "href"),
    )
end


function ProjectNarrativeBlock(; title, body, tags=String[])
    return ProjectNarrativeBlock(
        coerce_string(title, "title"),
        coerce_string(body, "body"),
        normalize_string_vector(tags, "tags"),
    )
end


function ProjectPagePayload(; payload_kind, schema_version, generated_at, snapshot, route_path="/project/", title, subtitle, breadcrumbs, anr_project_code, anr_project_url, anr_project_title, anr_context, facts, research_threads, collaboration_note)
    return ProjectPagePayload(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        coerce_string(title, "title"),
        coerce_string(subtitle, "subtitle"),
        breadcrumbs isa AbstractVector ? [item isa BreadcrumbItem ? item : breadcrumb_item_from_dict(item) for item in breadcrumbs] : error("breadcrumbs must be a list"),
        coerce_string(anr_project_code, "anr_project_code"),
        coerce_string(anr_project_url, "anr_project_url"),
        coerce_string(anr_project_title, "anr_project_title"),
        coerce_string(anr_context, "anr_context"),
        facts isa AbstractVector ? [fact isa ProjectFact ? fact : project_fact_from_dict(fact) for fact in facts] : error("facts must be a list"),
        research_threads isa AbstractVector ? [thread isa ProjectNarrativeBlock ? thread : project_narrative_block_from_dict(thread) for thread in research_threads] : error("research_threads must be a list"),
        coerce_string(collaboration_note, "collaboration_note"),
    )
end


function HistoryDetailPayload(; payload_kind, schema_version, generated_at, snapshot, route_path, title, breadcrumbs, summary, counts, benchmark_index_path, history_path, affected_problem_types=String[], affected_benchmark_names=String[], affected_objective_functions=String[], change_log)
    return HistoryDetailPayload(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        coerce_string(title, "title"),
        breadcrumbs isa AbstractVector ? [item isa BreadcrumbItem ? item : breadcrumb_item_from_dict(item) for item in breadcrumbs] : error("breadcrumbs must be a list"),
        coerce_string(summary, "summary"),
        counts isa SiteCounts ? counts : site_counts_from_dict(counts),
        validate_site_path(coerce_string(benchmark_index_path, "benchmark_index_path"), "benchmark_index_path"),
        validate_site_path(coerce_string(history_path, "history_path"), "history_path"),
        normalize_choice_vector(affected_problem_types, PROBLEM_TYPES, "affected_problem_types"),
        normalize_choice_vector(affected_benchmark_names, BENCHMARK_NAMES, "affected_benchmark_names"),
        normalize_choice_vector(affected_objective_functions, OBJECTIVE_FUNCTIONS, "affected_objective_functions"),
        change_log isa SnapshotChangeLog ? change_log : snapshot_change_log_from_dict(change_log),
    )
end


function BenchmarksIndexPayload(; payload_kind, schema_version, generated_at, snapshot, route_path, breadcrumbs=BreadcrumbItem[BreadcrumbItem("benchmarks", "/benchmarks/")], problems)
    return BenchmarksIndexPayload(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        breadcrumbs isa AbstractVector ? [item isa BreadcrumbItem ? item : breadcrumb_item_from_dict(item) for item in breadcrumbs] : error("breadcrumbs must be a list"),
        problems isa AbstractVector ? [problem isa ProblemSummaryCard ? problem : problem_summary_card_from_dict(problem) for problem in problems] : error("problems must be a list"),
    )
end


function ProblemIndexPayload(; payload_kind, schema_version, generated_at, snapshot, route_path, title, breadcrumbs, problem_type, summary, families)
    return ProblemIndexPayload(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        coerce_string(title, "title"),
        breadcrumbs isa AbstractVector ? [item isa BreadcrumbItem ? item : breadcrumb_item_from_dict(item) for item in breadcrumbs] : error("breadcrumbs must be a list"),
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        summary isa CatalogSummary ? summary : catalog_summary_from_dict(summary),
        families isa AbstractVector ? [family isa FamilySummaryCard ? family : family_summary_card_from_dict(family) for family in families] : error("families must be a list"),
    )
end


function CatalogIndexPayload(; payload_kind, schema_version, generated_at, snapshot, route_path, title, description=nothing, breadcrumbs, problem_type, benchmark_name, metric_variant=nothing, place_slug=nothing, size_bucket=nothing, summary, filter_facets=FilterFacet[], variant_routes=SubrouteEntry[], place_routes=SubrouteEntry[], size_routes=SubrouteEntry[], items=InstanceListItem[])
    metric_variant_value = coerce_optional_string(metric_variant, "metric_variant")
    metric_variant_value === nothing || require_choice(metric_variant_value, METRIC_VARIANTS, "metric_variant")
    return CatalogIndexPayload(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        coerce_string(title, "title"),
        coerce_optional_string(description, "description"),
        breadcrumbs isa AbstractVector ? [item isa BreadcrumbItem ? item : breadcrumb_item_from_dict(item) for item in breadcrumbs] : error("breadcrumbs must be a list"),
        require_choice(coerce_string(problem_type, "problem_type"), PROBLEM_TYPES, "problem_type"),
        require_choice(coerce_string(benchmark_name, "benchmark_name"), BENCHMARK_NAMES, "benchmark_name"),
        metric_variant_value,
        coerce_optional_string(place_slug, "place_slug"),
        coerce_optional_string(size_bucket, "size_bucket"),
        summary isa CatalogSummary ? summary : catalog_summary_from_dict(summary),
        filter_facets isa AbstractVector ? [facet isa FilterFacet ? facet : filter_facet_from_dict(facet) for facet in filter_facets] : error("filter_facets must be a list"),
        variant_routes isa AbstractVector ? [route isa SubrouteEntry ? route : subroute_entry_from_dict(route) for route in variant_routes] : error("variant_routes must be a list"),
        place_routes isa AbstractVector ? [route isa SubrouteEntry ? route : subroute_entry_from_dict(route) for route in place_routes] : error("place_routes must be a list"),
        size_routes isa AbstractVector ? [route isa SubrouteEntry ? route : subroute_entry_from_dict(route) for route in size_routes] : error("size_routes must be a list"),
        items isa AbstractVector ? [item isa InstanceListItem ? item : instance_list_item_from_dict(item) for item in items] : error("items must be a list"),
    )
end


function InstancePagePayload(; payload_kind, schema_version, generated_at, snapshot, route_path, title, breadcrumbs, locator, summary, artifact_links, sibling_variant_routes=Dict{String,String}(), derived_problem_routes=Dict{String,String}(), source_problem_routes=Dict{String,String}(), bks_entries=BKSPageEntry[], workbench_route_path="/workbench/")
    return InstancePagePayload(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        coerce_string(title, "title"),
        breadcrumbs isa AbstractVector ? [item isa BreadcrumbItem ? item : breadcrumb_item_from_dict(item) for item in breadcrumbs] : error("breadcrumbs must be a list"),
        locator isa BenchmarkLocator ? locator : benchmark_locator_from_dict(locator),
        summary isa InstancePageSummary ? summary : instance_page_summary_from_dict(summary),
        artifact_links isa SiteArtifactLinks ? artifact_links : site_artifact_links_from_dict(artifact_links),
        normalize_string_map(sibling_variant_routes, "sibling_variant_routes"),
        normalize_string_map(derived_problem_routes, "derived_problem_routes"),
        normalize_string_map(source_problem_routes, "source_problem_routes"),
        bks_entries isa AbstractVector ? [entry isa BKSPageEntry ? entry : bks_page_entry_from_dict(entry) for entry in bks_entries] : error("bks_entries must be a list"),
        validate_site_path(coerce_string(workbench_route_path, "workbench_route_path"), "workbench_route_path"),
    )
end


function ObjectivesPagePayload(; payload_kind, schema_version, generated_at, snapshot, route_path, title, breadcrumbs, explainers)
    return ObjectivesPagePayload(
        require_choice(coerce_string(payload_kind, "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind"),
        coerce_string(schema_version, "schema_version"),
        coerce_string(generated_at, "generated_at"),
        snapshot isa SnapshotRef ? snapshot : snapshot_ref_from_dict(snapshot),
        validate_site_path(coerce_string(route_path, "route_path"), "route_path"),
        coerce_string(title, "title"),
        breadcrumbs isa AbstractVector ? [item isa BreadcrumbItem ? item : breadcrumb_item_from_dict(item) for item in breadcrumbs] : error("breadcrumbs must be a list"),
        explainers isa AbstractVector ? [explainer isa ObjectiveExplainer ? explainer : objective_explainer_from_dict(explainer) for explainer in explainers] : error("explainers must be a list"),
    )
end


function ParsedVrpInstance(;
    name,
    vrp_type,
    comment=nothing,
    dimension,
    capacity,
    arc_costs,
    coordinates,
    demands,
    depot,
    service_times=nothing,
    time_windows=nothing,
)
    dimension_int = require_positive(coerce_int(dimension, "dimension"), "dimension")
    capacity_int = require_positive(coerce_int(capacity, "capacity"), "capacity")
    coordinates_vec = normalize_coordinate_vector(coordinates, "coordinates")
    demands_vec = normalize_int_vector(demands, "demands")
    depot_int = require_nonnegative(coerce_int(depot, "depot"), "depot")
    arc_costs_matrix = normalize_arc_costs(arc_costs)

    length(coordinates_vec) == dimension_int || error("coordinates length must match dimension")
    length(demands_vec) == dimension_int || error("demands length must match dimension")
    length(arc_costs_matrix) == dimension_int || error("arc_costs must have dimension rows")
    all(length(row) == dimension_int for row in arc_costs_matrix) || error("arc_costs must be a square matrix of size dimension")
    0 <= depot_int < dimension_int || error("depot must be in [0, $(dimension_int - 1)]")

    service_times_vec = nothing
    if service_times !== nothing
        service_times_vec = normalize_int_vector(service_times, "service_times")
        length(service_times_vec) == dimension_int || error("service_times length must match dimension")
    end

    time_windows_vec = nothing
    if time_windows !== nothing
        time_windows_vec = normalize_pair_int_vector(time_windows, "time_windows")
        length(time_windows_vec) == dimension_int || error("time_windows length must match dimension")
    end

    matrix_type = eltype(first(arc_costs_matrix))
    return ParsedVrpInstance{matrix_type}(
        coerce_string(name, "name"),
        require_choice(coerce_string(vrp_type, "vrp_type"), VRP_TYPES, "vrp_type"),
        coerce_optional_string(comment, "comment"),
        dimension_int,
        capacity_int,
        arc_costs_matrix,
        coordinates_vec,
        demands_vec,
        depot_int,
        service_times_vec,
        time_windows_vec,
    )
end


function artifact_paths_payload(value::ArtifactPaths)
    return [
        "vrp_json" => value.vrp_json,
        "vrp" => value.vrp,
        "meta" => value.meta,
        "manifest" => value.manifest,
    ]
end


function push_if_not_nothing!(pairs_vector::Vector{Pair{String,Any}}, key::String, value)
    value === nothing || push!(pairs_vector, key => value)
    return pairs_vector
end


function instance_metadata_payload(value::InstanceMetadata)
    result = Pair{String,Any}[
        "authors" => value.authors,
        "generated_at" => value.generated_at,
        "problem_type" => value.problem_type,
        "metric_variant" => value.metric_variant,
        "place_slug" => value.place_slug,
        "source_base_name" => value.source_base_name,
        "source_city" => value.source_city,
        "source_seed" => value.source_seed,
        "source_folder" => value.source_folder,
    ]
    push_if_not_nothing!(result, "num_vehicles_lb", value.num_vehicles_lb)
    push_if_not_nothing!(result, "submodule_git_commit", value.submodule_git_commit)
    push_if_not_nothing!(result, "generator_version", value.generator_version)
    push!(result, "artifact_paths" => artifact_paths_payload(value.artifact_paths))
    push!(result, "sibling_variant_paths" => value.sibling_variant_paths)
    push!(result, "derived_problem_paths" => value.derived_problem_paths)
    push!(result, "source_problem_paths" => value.source_problem_paths)
    return result
end


function historical_instance_payload(value::HistoricalBenchmarkInstance)
    result = Pair{String,Any}[
        "instance_name" => value.instance_name,
        "instance_origin" => value.instance_origin,
        "benchmark_name" => value.benchmark_name,
        "num_customers" => value.num_customers,
    ]
    push_if_not_nothing!(result, "num_vehicles", value.num_vehicles)
    push!(result, "vehicle_capacity" => value.vehicle_capacity)
    push!(result, "coordinates" => value.coordinates)
    push!(result, "demands" => value.demands)
    push!(result, "service_times" => value.service_times)
    push!(result, "time_windows" => value.time_windows)
    push!(result, "depot" => value.depot)
    push!(result, "arc_costs" => value.arc_costs)
    return result
end


function benchmark_instance_cvrp_payload(value::BenchmarkInstanceCVRP)
    result = Pair{String,Any}[
        "instance_id" => value.instance_id,
        "instance_origin" => value.instance_origin,
        "benchmark_name" => value.benchmark_name,
        "num_customers" => value.num_customers,
    ]
    push_if_not_nothing!(result, "num_vehicles", value.num_vehicles)
    push!(result, "vehicle_capacity" => value.vehicle_capacity)
    push!(result, "coordinates" => value.coordinates)
    push!(result, "demands" => value.demands)
    push!(result, "depot" => value.depot)
    push!(result, "arc_costs" => value.arc_costs)
    push!(result, "metadata" => instance_metadata_payload(value.metadata))
    return result
end


function benchmark_instance_vrptw_payload(value::BenchmarkInstanceVRPTW)
    result = Pair{String,Any}[
        "instance_id" => value.instance_id,
        "instance_origin" => value.instance_origin,
        "benchmark_name" => value.benchmark_name,
        "num_customers" => value.num_customers,
    ]
    push_if_not_nothing!(result, "num_vehicles", value.num_vehicles)
    push!(result, "vehicle_capacity" => value.vehicle_capacity)
    push!(result, "coordinates" => value.coordinates)
    push!(result, "demands" => value.demands)
    push!(result, "service_times" => value.service_times)
    push!(result, "time_windows" => value.time_windows)
    push!(result, "depot" => value.depot)
    push!(result, "arc_costs" => value.arc_costs)
    push!(result, "metadata" => instance_metadata_payload(value.metadata))
    return result
end


function benchmark_bks_payload(value::BenchmarkBKS)
    result = Pair{String,Any}[
        "instance_name" => value.instance_name,
        "objective_function" => value.objective_function,
        "routes" => value.routes,
    ]
    push_if_not_nothing!(result, "cost", value.cost)
    push!(result, "metadata" => value.metadata)
    return result
end


function snapshot_ref_payload(value::SnapshotRef)
    result = Pair{String,Any}[
        "snapshot_id" => value.snapshot_id,
        "published_at" => value.published_at,
        "source_commit" => value.source_commit,
    ]
    push_if_not_nothing!(result, "source_branch", value.source_branch)
    return result
end


site_counts_payload(value::SiteCounts) = Pair{String,Any}[
    "problem_count" => value.problem_count,
    "family_count" => value.family_count,
    "variant_count" => value.variant_count,
    "place_count" => value.place_count,
    "size_bucket_count" => value.size_bucket_count,
    "instance_count" => value.instance_count,
    "bks_count" => value.bks_count,
]


objective_availability_payload(value::ObjectiveAvailability) = Pair{String,Any}[
    "objective_function" => value.objective_function,
    "cost" => value.cost,
    "num_routes" => value.num_routes,
    "artifact_path" => value.artifact_path,
]


breadcrumb_item_payload(value::BreadcrumbItem) = Pair{String,Any}[
    "label" => value.label,
    "route_path" => value.route_path,
]


filter_option_payload(value::FilterOption) = Pair{String,Any}[
    "value" => value.value,
    "label" => value.label,
    "count" => value.count,
]


filter_facet_payload(value::FilterFacet) = Pair{String,Any}[
    "key" => value.key,
    "label" => value.label,
    "options" => [filter_option_payload(option) for option in value.options],
]


benchmark_locator_payload(value::BenchmarkLocator) = begin
    result = Pair{String,Any}[
        "problem_type" => value.problem_type,
        "benchmark_name" => value.benchmark_name,
    ]
    push_if_not_nothing!(result, "metric_variant", value.metric_variant)
    push_if_not_nothing!(result, "place_slug", value.place_slug)
    push!(result, "size_bucket" => value.size_bucket)
    push!(result, "instance_identifier" => value.instance_identifier)
    result
end


problem_summary_card_payload(value::ProblemSummaryCard) = Pair{String,Any}[
    "problem_type" => value.problem_type,
    "route_path" => value.route_path,
    "benchmark_names" => value.benchmark_names,
    "family_count" => value.family_count,
    "instance_count" => value.instance_count,
    "bks_count" => value.bks_count,
    "supported_objective_functions" => value.supported_objective_functions,
]


family_summary_card_payload(value::FamilySummaryCard) = Pair{String,Any}[
    "benchmark_name" => value.benchmark_name,
    "route_path" => value.route_path,
    "metric_variants" => value.metric_variants,
    "instance_count" => value.instance_count,
    "bks_count" => value.bks_count,
    "supported_objective_functions" => value.supported_objective_functions,
]


subroute_entry_payload(value::SubrouteEntry) = Pair{String,Any}[
    "key" => value.key,
    "label" => value.label,
    "route_path" => value.route_path,
    "instance_count" => value.instance_count,
    "bks_count" => value.bks_count,
]


objective_explainer_payload(value::ObjectiveExplainer) = Pair{String,Any}[
    "objective_function" => value.objective_function,
    "short_label" => value.short_label,
    "title" => value.title,
    "description" => value.description,
    "interpretation_notes" => value.interpretation_notes,
    "related_routes" => [subroute_entry_payload(route) for route in value.related_routes],
]


catalog_summary_payload(value::CatalogSummary) = Pair{String,Any}[
    "instance_count" => value.instance_count,
    "bks_count" => value.bks_count,
    "place_count" => value.place_count,
    "size_bucket_count" => value.size_bucket_count,
    "supported_objective_functions" => value.supported_objective_functions,
]


instance_list_item_payload(value::InstanceListItem) = begin
    result = Pair{String,Any}[
        "locator" => benchmark_locator_payload(value.locator),
        "display_name" => value.display_name,
        "route_path" => value.route_path,
        "artifact_vrp_json_path" => value.artifact_vrp_json_path,
    ]
    push_if_not_nothing!(result, "place_slug", value.place_slug)
    push_if_not_nothing!(result, "historical_topology_type", value.historical_topology_type)
    push_if_not_nothing!(result, "historical_tw_type", value.historical_tw_type)
    push!(result, "bks_count" => value.bks_count)
    push!(result, "viewer_render_mode" => value.viewer_render_mode)
    push!(result, "road_cache_status" => value.road_cache_status)
    push!(result, "objective_availability" => [objective_availability_payload(entry) for entry in value.objective_availability])
    result
end


site_artifact_links_payload(value::SiteArtifactLinks) = begin
    result = Pair{String,Any}["vrp_json_path" => value.vrp_json_path]
    push_if_not_nothing!(result, "vrp_path", value.vrp_path)
    push_if_not_nothing!(result, "meta_path", value.meta_path)
    push_if_not_nothing!(result, "manifest_path", value.manifest_path)
    result
end


bks_page_entry_payload(value::BKSPageEntry) = begin
    result = Pair{String,Any}[
        "objective_function" => value.objective_function,
        "artifact_path" => value.artifact_path,
        "num_routes" => value.num_routes,
    ]
    push_if_not_nothing!(result, "cost", value.cost)
    push_if_not_nothing!(result, "authors", value.authors)
    push_if_not_nothing!(result, "source", value.source)
    push_if_not_nothing!(result, "method", value.method)
    push_if_not_nothing!(result, "validated_num_routes", value.validated_num_routes)
    result
end


instance_page_summary_payload(value::InstancePageSummary) = begin
    result = Pair{String,Any}[
        "display_name" => value.display_name,
        "problem_type" => value.problem_type,
        "benchmark_name" => value.benchmark_name,
    ]
    push_if_not_nothing!(result, "metric_variant", value.metric_variant)
    push_if_not_nothing!(result, "place_slug", value.place_slug)
    push!(result, "size_bucket" => value.size_bucket)
    push!(result, "num_customers" => value.num_customers)
    push_if_not_nothing!(result, "historical_topology_type", value.historical_topology_type)
    push_if_not_nothing!(result, "historical_tw_type", value.historical_tw_type)
    push_if_not_nothing!(result, "num_vehicles", value.num_vehicles)
    push_if_not_nothing!(result, "num_vehicles_lb", value.num_vehicles_lb)
    push!(result, "vehicle_capacity" => value.vehicle_capacity)
    push_if_not_nothing!(result, "authors", value.authors)
    push_if_not_nothing!(result, "generated_at", value.generated_at)
    push_if_not_nothing!(result, "source_city", value.source_city)
    push!(result, "has_geometry_sidecar" => value.has_geometry_sidecar)
    push!(result, "viewer_render_mode" => value.viewer_render_mode)
    push!(result, "road_cache_status" => value.road_cache_status)
    push!(result, "road_cache_metrics" => value.road_cache_metrics)
    push!(result, "road_cache_entry_count" => value.road_cache_entry_count)
    push_if_not_nothing!(result, "road_cache_expected_entry_count", value.road_cache_expected_entry_count)
    push!(result, "supported_objective_functions" => value.supported_objective_functions)
    result
end


site_snapshot_manifest_payload(value::SiteSnapshotManifest) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "summary" => value.summary,
    "counts" => site_counts_payload(value.counts),
    "benchmark_index_path" => value.benchmark_index_path,
    "history_path" => value.history_path,
    "history_detail_path" => value.history_detail_path,
]


site_history_entry_payload(value::SiteHistoryEntry) = Pair{String,Any}[
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "summary" => value.summary,
    "detail_route_path" => value.detail_route_path,
    "affected_problem_types" => value.affected_problem_types,
    "affected_benchmark_names" => value.affected_benchmark_names,
    "affected_objective_functions" => value.affected_objective_functions,
]


site_history_ledger_payload(value::SiteHistoryLedger) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "current_snapshot_id" => value.current_snapshot_id,
    "entries" => [site_history_entry_payload(entry) for entry in value.entries],
]


home_page_payload(value::HomePagePayload) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "route_path" => value.route_path,
    "title" => value.title,
    "subtitle" => value.subtitle,
    "hero_summary" => value.hero_summary,
    "latest_publication_summary" => value.latest_publication_summary,
    "counts" => site_counts_payload(value.counts),
    "problems" => [problem_summary_card_payload(problem) for problem in value.problems],
    "benchmarks_route_path" => value.benchmarks_route_path,
    "project_route_path" => value.project_route_path,
    "objectives_route_path" => value.objectives_route_path,
    "history_route_path" => value.history_route_path,
    "workbench_route_path" => value.workbench_route_path,
]


project_fact_payload(value::ProjectFact) = begin
    result = Pair{String,Any}[
        "label" => value.label,
        "value" => value.value,
    ]
    push_if_not_nothing!(result, "href", value.href)
    result
end


project_narrative_block_payload(value::ProjectNarrativeBlock) = Pair{String,Any}[
    "title" => value.title,
    "body" => value.body,
    "tags" => value.tags,
]


project_page_payload(value::ProjectPagePayload) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "route_path" => value.route_path,
    "title" => value.title,
    "subtitle" => value.subtitle,
    "breadcrumbs" => [breadcrumb_item_payload(item) for item in value.breadcrumbs],
    "anr_project_code" => value.anr_project_code,
    "anr_project_url" => value.anr_project_url,
    "anr_project_title" => value.anr_project_title,
    "anr_context" => value.anr_context,
    "facts" => [project_fact_payload(fact) for fact in value.facts],
    "research_threads" => [project_narrative_block_payload(thread) for thread in value.research_threads],
    "collaboration_note" => value.collaboration_note,
]


history_detail_payload(value::HistoryDetailPayload) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "route_path" => value.route_path,
    "title" => value.title,
    "breadcrumbs" => [breadcrumb_item_payload(item) for item in value.breadcrumbs],
    "summary" => value.summary,
    "counts" => site_counts_payload(value.counts),
    "benchmark_index_path" => value.benchmark_index_path,
    "history_path" => value.history_path,
    "affected_problem_types" => value.affected_problem_types,
    "affected_benchmark_names" => value.affected_benchmark_names,
    "affected_objective_functions" => value.affected_objective_functions,
]


benchmarks_index_payload(value::BenchmarksIndexPayload) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "route_path" => value.route_path,
    "breadcrumbs" => [breadcrumb_item_payload(item) for item in value.breadcrumbs],
    "problems" => [problem_summary_card_payload(problem) for problem in value.problems],
]


problem_index_payload(value::ProblemIndexPayload) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "route_path" => value.route_path,
    "title" => value.title,
    "breadcrumbs" => [breadcrumb_item_payload(item) for item in value.breadcrumbs],
    "problem_type" => value.problem_type,
    "summary" => catalog_summary_payload(value.summary),
    "families" => [family_summary_card_payload(family) for family in value.families],
]


catalog_index_payload(value::CatalogIndexPayload) = begin
    result = Pair{String,Any}[
        "payload_kind" => value.payload_kind,
        "schema_version" => value.schema_version,
        "generated_at" => value.generated_at,
        "snapshot" => snapshot_ref_payload(value.snapshot),
        "route_path" => value.route_path,
        "title" => value.title,
        "breadcrumbs" => [breadcrumb_item_payload(item) for item in value.breadcrumbs],
        "problem_type" => value.problem_type,
        "benchmark_name" => value.benchmark_name,
        "summary" => catalog_summary_payload(value.summary),
        "filter_facets" => [filter_facet_payload(facet) for facet in value.filter_facets],
        "variant_routes" => [subroute_entry_payload(route) for route in value.variant_routes],
        "place_routes" => [subroute_entry_payload(route) for route in value.place_routes],
        "size_routes" => [subroute_entry_payload(route) for route in value.size_routes],
        "items" => [instance_list_item_payload(item) for item in value.items],
    ]
    push_if_not_nothing!(result, "description", value.description)
    push_if_not_nothing!(result, "metric_variant", value.metric_variant)
    push_if_not_nothing!(result, "place_slug", value.place_slug)
    push_if_not_nothing!(result, "size_bucket", value.size_bucket)
    result
end


instance_page_payload(value::InstancePagePayload) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "route_path" => value.route_path,
    "title" => value.title,
    "breadcrumbs" => [breadcrumb_item_payload(item) for item in value.breadcrumbs],
    "locator" => benchmark_locator_payload(value.locator),
    "summary" => instance_page_summary_payload(value.summary),
    "artifact_links" => site_artifact_links_payload(value.artifact_links),
    "sibling_variant_routes" => value.sibling_variant_routes,
    "derived_problem_routes" => value.derived_problem_routes,
    "source_problem_routes" => value.source_problem_routes,
    "bks_entries" => [bks_page_entry_payload(entry) for entry in value.bks_entries],
    "workbench_route_path" => value.workbench_route_path,
]


objectives_page_payload(value::ObjectivesPagePayload) = Pair{String,Any}[
    "payload_kind" => value.payload_kind,
    "schema_version" => value.schema_version,
    "generated_at" => value.generated_at,
    "snapshot" => snapshot_ref_payload(value.snapshot),
    "route_path" => value.route_path,
    "title" => value.title,
    "breadcrumbs" => [breadcrumb_item_payload(item) for item in value.breadcrumbs],
    "explainers" => [objective_explainer_payload(explainer) for explainer in value.explainers],
]


payload(value::ArtifactPaths) = artifact_paths_payload(value)
payload(value::InstanceMetadata) = instance_metadata_payload(value)
payload(value::HistoricalBenchmarkInstance) = historical_instance_payload(value)
payload(value::BenchmarkInstanceCVRP) = benchmark_instance_cvrp_payload(value)
payload(value::BenchmarkInstanceVRPTW) = benchmark_instance_vrptw_payload(value)
payload(value::BenchmarkBKS) = benchmark_bks_payload(value)
payload(value::SnapshotRef) = snapshot_ref_payload(value)
payload(value::SiteCounts) = site_counts_payload(value)
payload(value::ObjectiveAvailability) = objective_availability_payload(value)
payload(value::BreadcrumbItem) = breadcrumb_item_payload(value)
payload(value::FilterOption) = filter_option_payload(value)
payload(value::FilterFacet) = filter_facet_payload(value)
payload(value::BenchmarkLocator) = benchmark_locator_payload(value)
payload(value::ProblemSummaryCard) = problem_summary_card_payload(value)
payload(value::FamilySummaryCard) = family_summary_card_payload(value)
payload(value::SubrouteEntry) = subroute_entry_payload(value)
payload(value::ObjectiveExplainer) = objective_explainer_payload(value)
payload(value::ProjectFact) = project_fact_payload(value)
payload(value::ProjectNarrativeBlock) = project_narrative_block_payload(value)
payload(value::CatalogSummary) = catalog_summary_payload(value)
payload(value::InstanceListItem) = instance_list_item_payload(value)
payload(value::SiteArtifactLinks) = site_artifact_links_payload(value)
payload(value::BKSPageEntry) = bks_page_entry_payload(value)
payload(value::InstancePageSummary) = instance_page_summary_payload(value)
payload(value::SiteSnapshotManifest) = site_snapshot_manifest_payload(value)
payload(value::SiteHistoryEntry) = site_history_entry_payload(value)
payload(value::SiteHistoryLedger) = site_history_ledger_payload(value)
payload(value::HomePagePayload) = home_page_payload(value)
payload(value::ProjectPagePayload) = project_page_payload(value)
payload(value::HistoryDetailPayload) = history_detail_payload(value)
payload(value::BenchmarksIndexPayload) = benchmarks_index_payload(value)
payload(value::ProblemIndexPayload) = problem_index_payload(value)
payload(value::CatalogIndexPayload) = catalog_index_payload(value)
payload(value::InstancePagePayload) = instance_page_payload(value)
payload(value::ObjectivesPagePayload) = objectives_page_payload(value)
payload(value::NamedTuple) = [String(name) => getfield(value, name) for name in propertynames(value)]
payload(value::AbstractDict) = [String(key) => nested for (key, nested) in pairs(value)]
payload(value::AbstractVector{<:Pair}) = [String(pair.first) => pair.second for pair in value]


function tuple_json_encode(value::Tuple; indent::Int, level::Int, sort_keys::Bool)
    encoded_items = [custom_json_encode(item; indent=indent, level=level, sort_keys=sort_keys) for item in value]
    return "[" * join(encoded_items, ", ") * "]"
end


function custom_json_encode(value::ArtifactPaths; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::InstanceMetadata; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::HistoricalBenchmarkInstance; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::BenchmarkInstanceCVRP; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::BenchmarkInstanceVRPTW; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::BenchmarkBKS; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::SnapshotRef; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::SiteCounts; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::ObjectiveAvailability; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::BreadcrumbItem; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::FilterOption; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::FilterFacet; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::BenchmarkLocator; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::ProblemSummaryCard; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::FamilySummaryCard; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::SubrouteEntry; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::ObjectiveExplainer; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::CatalogSummary; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::InstanceListItem; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::SiteArtifactLinks; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::BKSPageEntry; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::InstancePageSummary; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::SiteSnapshotManifest; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::SiteHistoryEntry; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::SiteHistoryLedger; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::HomePagePayload; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::ProjectPagePayload; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::HistoryDetailPayload; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::BenchmarksIndexPayload; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::ProblemIndexPayload; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::CatalogIndexPayload; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::InstancePagePayload; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::ObjectivesPagePayload; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::NamedTuple; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::AbstractDict; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return custom_json_encode(payload(value); indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value::AbstractVector{<:Pair}; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    current_indent = indent_prefix(level, indent)
    next_indent = indent_prefix(level + 1, indent)
    entries = payload(value)
    sort_keys && sort!(entries, by=first)

    isempty(entries) && return "{}"

    items = String[]
    for (key, nested) in entries
        encoded_value = custom_json_encode(nested; indent=indent, level=level + 1, sort_keys=sort_keys)
        push!(items, next_indent * json_scalar_string(key) * ": " * encoded_value)
    end
    return "{\n" * join(items, ",\n") * "\n" * current_indent * "}"
end


function custom_json_encode(values::AbstractVector; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    isempty(values) && return "[]"

    current_indent = indent_prefix(level, indent)
    next_indent = indent_prefix(level + 1, indent)

    if all(value -> value isa Real && !(value isa Bool), values)
        return "[" * join((json_scalar_string(value) for value in values), ", ") * "]"
    end

    if all(value -> value isa AbstractString, values)
        return "[" * join((json_scalar_string(value) for value in values), ", ") * "]"
    end

    if all(value -> value isa Tuple, values)
        items = [next_indent * tuple_json_encode(value; indent=indent, level=level + 1, sort_keys=sort_keys) for value in values]
        return "[\n" * join(items, ",\n") * "\n" * current_indent * "]"
    end

    if all(value -> value isa AbstractVector, values)
        items = [next_indent * custom_json_encode(value; indent=indent, level=level + 1, sort_keys=sort_keys) for value in values]
        return "[\n" * join(items, ",\n") * "\n" * current_indent * "]"
    end

    items = [next_indent * custom_json_encode(value; indent=indent, level=level + 1, sort_keys=sort_keys) for value in values]
    return "[\n" * join(items, ",\n") * "\n" * current_indent * "]"
end


function custom_json_encode(value::Tuple; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return tuple_json_encode(value; indent=indent, level=level, sort_keys=sort_keys)
end


function custom_json_encode(value; indent::Int=4, level::Int=0, sort_keys::Bool=false)
    return json_scalar_string(value)
end


function get_custom_json_string(value; indent::Int=4, sort_keys::Bool=false)
    return custom_json_encode(value; indent=indent, level=0, sort_keys=sort_keys)
end


function materialize_json(value)
    if value isa JSON3.Object
        return Dict(String(key) => materialize_json(nested) for (key, nested) in pairs(value))
    end
    if value isa JSON3.Array
        return [materialize_json(nested) for nested in value]
    end
    return value
end


function load_json_from_file(filepath::AbstractString)
    return materialize_json(JSON3.read(read(filepath, String)))
end


function save_json_to_file(value, filepath::AbstractString; indent::Int=4, sort_keys::Bool=false)
    mkpath(dirname(filepath))
    open(filepath, "w") do io
        write(io, get_custom_json_string(value; indent=indent, sort_keys=sort_keys))
        write(io, "\n")
    end
    return filepath
end


function artifact_paths_from_dict(payload::AbstractDict)
    ensure_allowed_keys(payload, Set(["vrp_json", "vrp", "meta", "manifest"]), "ArtifactPaths")
    return ArtifactPaths(
        vrp_json=require_field(payload, "vrp_json"),
        vrp=require_field(payload, "vrp"),
        meta=require_field(payload, "meta"),
        manifest=require_field(payload, "manifest"),
    )
end


function instance_metadata_from_dict(payload::AbstractDict)
    allowed = Set([
        "authors",
        "generated_at",
        "problem_type",
        "metric_variant",
        "place_slug",
        "source_base_name",
        "source_city",
        "source_seed",
        "source_folder",
        "num_vehicles_lb",
        "submodule_git_commit",
        "generator_version",
        "artifact_paths",
        "sibling_variant_paths",
        "derived_problem_paths",
        "source_problem_paths",
    ])
    ensure_allowed_keys(payload, allowed, "InstanceMetadata")
    return InstanceMetadata(
        authors=require_field(payload, "authors"),
        generated_at=require_field(payload, "generated_at"),
        problem_type=require_field(payload, "problem_type"),
        metric_variant=require_field(payload, "metric_variant"),
        place_slug=require_field(payload, "place_slug"),
        source_base_name=require_field(payload, "source_base_name"),
        source_city=require_field(payload, "source_city"),
        source_seed=require_field(payload, "source_seed"),
        source_folder=require_field(payload, "source_folder"),
        num_vehicles_lb=get(payload, "num_vehicles_lb", nothing),
        submodule_git_commit=get(payload, "submodule_git_commit", nothing),
        generator_version=get(payload, "generator_version", nothing),
        artifact_paths=artifact_paths_from_dict(require_field(payload, "artifact_paths")),
        sibling_variant_paths=get(payload, "sibling_variant_paths", Dict{String,String}()),
        derived_problem_paths=get(payload, "derived_problem_paths", Dict{String,String}()),
        source_problem_paths=get(payload, "source_problem_paths", Dict{String,String}()),
    )
end


function historical_benchmark_instance_from_dict(payload::AbstractDict)
    allowed = Set([
        "instance_name",
        "instance_origin",
        "benchmark_name",
        "num_customers",
        "num_vehicles",
        "vehicle_capacity",
        "coordinates",
        "demands",
        "service_times",
        "time_windows",
        "depot",
        "arc_costs",
    ])
    ensure_allowed_keys(payload, allowed, "HistoricalBenchmarkInstance")
    return HistoricalBenchmarkInstance(
        instance_name=require_field(payload, "instance_name"),
        instance_origin=require_field(payload, "instance_origin"),
        benchmark_name=require_field(payload, "benchmark_name"),
        num_customers=require_field(payload, "num_customers"),
        num_vehicles=get(payload, "num_vehicles", nothing),
        vehicle_capacity=require_field(payload, "vehicle_capacity"),
        coordinates=require_field(payload, "coordinates"),
        demands=require_field(payload, "demands"),
        service_times=require_field(payload, "service_times"),
        time_windows=require_field(payload, "time_windows"),
        depot=get(payload, "depot", 0),
        arc_costs=require_field(payload, "arc_costs"),
    )
end


function historical_benchmark_instance_from_legacy_dict(payload::AbstractDict)
    haskey(payload, "arc_costs") && error("Legacy instance already contains 'arc_costs'")
    haskey(payload, "arc_travel_times") || error("Legacy instance is missing required field 'arc_travel_times'")
    migrated = Dict{String,Any}(String(key) => value for (key, value) in pairs(payload))
    migrated["arc_costs"] = pop!(migrated, "arc_travel_times")
    return historical_benchmark_instance_from_dict(migrated)
end


function benchmark_instance_cvrp_from_dict(payload::AbstractDict)
    allowed = Set([
        "instance_id",
        "instance_origin",
        "benchmark_name",
        "num_customers",
        "num_vehicles",
        "vehicle_capacity",
        "coordinates",
        "demands",
        "depot",
        "arc_costs",
        "metadata",
    ])
    ensure_allowed_keys(payload, allowed, "BenchmarkInstanceCVRP")
    return BenchmarkInstanceCVRP(
        instance_id=require_field(payload, "instance_id"),
        instance_origin=require_field(payload, "instance_origin"),
        benchmark_name=require_field(payload, "benchmark_name"),
        num_customers=require_field(payload, "num_customers"),
        num_vehicles=get(payload, "num_vehicles", nothing),
        vehicle_capacity=require_field(payload, "vehicle_capacity"),
        coordinates=require_field(payload, "coordinates"),
        demands=require_field(payload, "demands"),
        depot=get(payload, "depot", 0),
        arc_costs=require_field(payload, "arc_costs"),
        metadata=instance_metadata_from_dict(require_field(payload, "metadata")),
    )
end


function benchmark_instance_vrptw_from_dict(payload::AbstractDict)
    allowed = Set([
        "instance_id",
        "instance_origin",
        "benchmark_name",
        "num_customers",
        "num_vehicles",
        "vehicle_capacity",
        "coordinates",
        "demands",
        "service_times",
        "time_windows",
        "depot",
        "arc_costs",
        "metadata",
    ])
    ensure_allowed_keys(payload, allowed, "BenchmarkInstanceVRPTW")
    return BenchmarkInstanceVRPTW(
        instance_id=require_field(payload, "instance_id"),
        instance_origin=require_field(payload, "instance_origin"),
        benchmark_name=require_field(payload, "benchmark_name"),
        num_customers=require_field(payload, "num_customers"),
        num_vehicles=get(payload, "num_vehicles", nothing),
        vehicle_capacity=require_field(payload, "vehicle_capacity"),
        coordinates=require_field(payload, "coordinates"),
        demands=require_field(payload, "demands"),
        service_times=require_field(payload, "service_times"),
        time_windows=require_field(payload, "time_windows"),
        depot=get(payload, "depot", 0),
        arc_costs=require_field(payload, "arc_costs"),
        metadata=instance_metadata_from_dict(require_field(payload, "metadata")),
    )
end


function benchmark_bks_from_dict(payload::AbstractDict)
    allowed = Set(["instance_name", "objective_function", "routes", "cost", "metadata"])
    ensure_allowed_keys(payload, allowed, "BenchmarkBKS")
    return BenchmarkBKS(
        instance_name=require_field(payload, "instance_name"),
        objective_function=require_field(payload, "objective_function"),
        routes=require_field(payload, "routes"),
        cost=get(payload, "cost", nothing),
        metadata=get(payload, "metadata", Dict{String,Any}()),
    )
end


function snapshot_ref_from_dict(payload::AbstractDict)
    allowed = Set(["snapshot_id", "published_at", "source_commit", "source_branch"])
    ensure_allowed_keys(payload, allowed, "SnapshotRef")
    return SnapshotRef(
        snapshot_id=require_field(payload, "snapshot_id"),
        published_at=require_field(payload, "published_at"),
        source_commit=require_field(payload, "source_commit"),
        source_branch=get(payload, "source_branch", nothing),
    )
end


function site_counts_from_dict(payload::AbstractDict)
    allowed = Set(["problem_count", "family_count", "variant_count", "place_count", "size_bucket_count", "instance_count", "bks_count"])
    ensure_allowed_keys(payload, allowed, "SiteCounts")
    return SiteCounts(
        problem_count=require_field(payload, "problem_count"),
        family_count=require_field(payload, "family_count"),
        variant_count=require_field(payload, "variant_count"),
        place_count=require_field(payload, "place_count"),
        size_bucket_count=require_field(payload, "size_bucket_count"),
        instance_count=require_field(payload, "instance_count"),
        bks_count=require_field(payload, "bks_count"),
    )
end


function objective_availability_from_dict(payload::AbstractDict)
    allowed = Set(["objective_function", "cost", "num_routes", "artifact_path"])
    ensure_allowed_keys(payload, allowed, "ObjectiveAvailability")
    return ObjectiveAvailability(
        objective_function=require_field(payload, "objective_function"),
        cost=get(payload, "cost", nothing),
        num_routes=get(payload, "num_routes", nothing),
        artifact_path=require_field(payload, "artifact_path"),
    )
end


function breadcrumb_item_from_dict(payload::AbstractDict)
    allowed = Set(["label", "route_path"])
    ensure_allowed_keys(payload, allowed, "BreadcrumbItem")
    return BreadcrumbItem(
        label=require_field(payload, "label"),
        route_path=require_field(payload, "route_path"),
    )
end


function filter_option_from_dict(payload::AbstractDict)
    allowed = Set(["value", "label", "count"])
    ensure_allowed_keys(payload, allowed, "FilterOption")
    return FilterOption(
        value=require_field(payload, "value"),
        label=require_field(payload, "label"),
        count=require_field(payload, "count"),
    )
end


function filter_facet_from_dict(payload::AbstractDict)
    allowed = Set(["key", "label", "options"])
    ensure_allowed_keys(payload, allowed, "FilterFacet")
    return FilterFacet(
        key=require_field(payload, "key"),
        label=require_field(payload, "label"),
        options=require_field(payload, "options"),
    )
end


function benchmark_locator_from_dict(payload::AbstractDict)
    allowed = Set(["problem_type", "benchmark_name", "metric_variant", "place_slug", "size_bucket", "instance_identifier"])
    ensure_allowed_keys(payload, allowed, "BenchmarkLocator")
    return BenchmarkLocator(
        problem_type=require_field(payload, "problem_type"),
        benchmark_name=require_field(payload, "benchmark_name"),
        metric_variant=get(payload, "metric_variant", nothing),
        place_slug=get(payload, "place_slug", nothing),
        size_bucket=require_field(payload, "size_bucket"),
        instance_identifier=require_field(payload, "instance_identifier"),
    )
end


function problem_summary_card_from_dict(payload::AbstractDict)
    allowed = Set(["problem_type", "route_path", "benchmark_names", "family_count", "instance_count", "bks_count", "supported_objective_functions"])
    ensure_allowed_keys(payload, allowed, "ProblemSummaryCard")
    return ProblemSummaryCard(
        problem_type=require_field(payload, "problem_type"),
        route_path=require_field(payload, "route_path"),
        benchmark_names=require_field(payload, "benchmark_names"),
        family_count=require_field(payload, "family_count"),
        instance_count=require_field(payload, "instance_count"),
        bks_count=require_field(payload, "bks_count"),
        supported_objective_functions=require_field(payload, "supported_objective_functions"),
    )
end


function family_summary_card_from_dict(payload::AbstractDict)
    allowed = Set(["benchmark_name", "route_path", "metric_variants", "instance_count", "bks_count", "supported_objective_functions"])
    ensure_allowed_keys(payload, allowed, "FamilySummaryCard")
    return FamilySummaryCard(
        benchmark_name=require_field(payload, "benchmark_name"),
        route_path=require_field(payload, "route_path"),
        metric_variants=require_field(payload, "metric_variants"),
        instance_count=require_field(payload, "instance_count"),
        bks_count=require_field(payload, "bks_count"),
        supported_objective_functions=require_field(payload, "supported_objective_functions"),
    )
end


function subroute_entry_from_dict(payload::AbstractDict)
    allowed = Set(["key", "label", "route_path", "instance_count", "bks_count"])
    ensure_allowed_keys(payload, allowed, "SubrouteEntry")
    return SubrouteEntry(
        key=require_field(payload, "key"),
        label=require_field(payload, "label"),
        route_path=require_field(payload, "route_path"),
        instance_count=require_field(payload, "instance_count"),
        bks_count=require_field(payload, "bks_count"),
    )
end


function objective_explainer_from_dict(payload::AbstractDict)
    allowed = Set(["objective_function", "short_label", "title", "description", "interpretation_notes", "related_routes"])
    ensure_allowed_keys(payload, allowed, "ObjectiveExplainer")
    return ObjectiveExplainer(
        objective_function=require_field(payload, "objective_function"),
        short_label=require_field(payload, "short_label"),
        title=require_field(payload, "title"),
        description=require_field(payload, "description"),
        interpretation_notes=require_field(payload, "interpretation_notes"),
        related_routes=get(payload, "related_routes", SubrouteEntry[]),
    )
end


function catalog_summary_from_dict(payload::AbstractDict)
    allowed = Set(["instance_count", "bks_count", "place_count", "size_bucket_count", "supported_objective_functions"])
    ensure_allowed_keys(payload, allowed, "CatalogSummary")
    return CatalogSummary(
        instance_count=require_field(payload, "instance_count"),
        bks_count=require_field(payload, "bks_count"),
        place_count=require_field(payload, "place_count"),
        size_bucket_count=require_field(payload, "size_bucket_count"),
        supported_objective_functions=require_field(payload, "supported_objective_functions"),
    )
end


function instance_list_item_from_dict(payload::AbstractDict)
    allowed = Set(["locator", "display_name", "instance_id", "num_customers", "route_path", "artifact_vrp_json_path", "place_slug", "historical_topology_type", "historical_tw_type", "bks_count", "viewer_render_mode", "road_cache_status", "objective_availability"])
    ensure_allowed_keys(payload, allowed, "InstanceListItem")
    return InstanceListItem(
        locator=require_field(payload, "locator"),
        display_name=require_field(payload, "display_name"),
        instance_id=require_field(payload, "instance_id"),
        num_customers=require_field(payload, "num_customers"),
        route_path=require_field(payload, "route_path"),
        artifact_vrp_json_path=require_field(payload, "artifact_vrp_json_path"),
        place_slug=get(payload, "place_slug", nothing),
        historical_topology_type=get(payload, "historical_topology_type", nothing),
        historical_tw_type=get(payload, "historical_tw_type", nothing),
        bks_count=require_field(payload, "bks_count"),
        viewer_render_mode=get(payload, "viewer_render_mode", "straight_line"),
        road_cache_status=get(payload, "road_cache_status", "not_applicable"),
        objective_availability=require_field(payload, "objective_availability"),
    )
end


function site_artifact_links_from_dict(payload::AbstractDict)
    allowed = Set(["vrp_json_path", "vrp_path", "meta_path", "manifest_path"])
    ensure_allowed_keys(payload, allowed, "SiteArtifactLinks")
    return SiteArtifactLinks(
        vrp_json_path=require_field(payload, "vrp_json_path"),
        vrp_path=get(payload, "vrp_path", nothing),
        meta_path=get(payload, "meta_path", nothing),
        manifest_path=get(payload, "manifest_path", nothing),
    )
end


function bks_page_entry_from_dict(payload::AbstractDict)
    allowed = Set(["objective_function", "artifact_path", "num_routes", "cost", "authors", "source", "method", "validated_num_routes"])
    ensure_allowed_keys(payload, allowed, "BKSPageEntry")
    return BKSPageEntry(
        objective_function=require_field(payload, "objective_function"),
        artifact_path=require_field(payload, "artifact_path"),
        num_routes=require_field(payload, "num_routes"),
        cost=get(payload, "cost", nothing),
        authors=get(payload, "authors", nothing),
        source=get(payload, "source", nothing),
        method=get(payload, "method", nothing),
        validated_num_routes=get(payload, "validated_num_routes", nothing),
    )
end


function instance_page_summary_from_dict(payload::AbstractDict)
    allowed = Set(["display_name", "problem_type", "benchmark_name", "metric_variant", "place_slug", "size_bucket", "num_customers", "historical_topology_type", "historical_tw_type", "num_vehicles", "num_vehicles_lb", "vehicle_capacity", "authors", "generated_at", "source_city", "has_geometry_sidecar", "viewer_render_mode", "road_cache_status", "road_cache_metrics", "road_cache_entry_count", "road_cache_expected_entry_count", "supported_objective_functions"])
    ensure_allowed_keys(payload, allowed, "InstancePageSummary")
    return InstancePageSummary(
        display_name=require_field(payload, "display_name"),
        problem_type=require_field(payload, "problem_type"),
        benchmark_name=require_field(payload, "benchmark_name"),
        metric_variant=get(payload, "metric_variant", nothing),
        place_slug=get(payload, "place_slug", nothing),
        size_bucket=require_field(payload, "size_bucket"),
        num_customers=require_field(payload, "num_customers"),
        historical_topology_type=get(payload, "historical_topology_type", nothing),
        historical_tw_type=get(payload, "historical_tw_type", nothing),
        num_vehicles=get(payload, "num_vehicles", nothing),
        num_vehicles_lb=get(payload, "num_vehicles_lb", nothing),
        vehicle_capacity=require_field(payload, "vehicle_capacity"),
        authors=get(payload, "authors", nothing),
        generated_at=get(payload, "generated_at", nothing),
        source_city=get(payload, "source_city", nothing),
        has_geometry_sidecar=get(payload, "has_geometry_sidecar", false),
        viewer_render_mode=get(payload, "viewer_render_mode", "straight_line"),
        road_cache_status=get(payload, "road_cache_status", "not_applicable"),
        road_cache_metrics=get(payload, "road_cache_metrics", String[]),
        road_cache_entry_count=get(payload, "road_cache_entry_count", 0),
        road_cache_expected_entry_count=get(payload, "road_cache_expected_entry_count", nothing),
        supported_objective_functions=require_field(payload, "supported_objective_functions"),
    )
end


function site_snapshot_manifest_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "summary", "counts", "benchmark_index_path", "history_path", "history_detail_path"])
    ensure_allowed_keys(payload, allowed, "SiteSnapshotManifest")
    return SiteSnapshotManifest(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        summary=require_field(payload, "summary"),
        counts=require_field(payload, "counts"),
        benchmark_index_path=require_field(payload, "benchmark_index_path"),
        history_path=require_field(payload, "history_path"),
        history_detail_path=require_field(payload, "history_detail_path"),
    )
end


function bks_value_from_dict(payload::AbstractDict)
    allowed = Set(["cost", "num_routes", "authors", "method"])
    ensure_allowed_keys(payload, allowed, "BksValue")
    return BksValue(
        cost=get(payload, "cost", nothing),
        num_routes=get(payload, "num_routes", nothing),
        authors=get(payload, "authors", nothing),
        method=get(payload, "method", nothing),
    )
end


function family_change_from_dict(payload::AbstractDict)
    allowed = Set(["problem_type", "benchmark_name", "kind"])
    ensure_allowed_keys(payload, allowed, "FamilyChange")
    return FamilyChange(
        problem_type=require_field(payload, "problem_type"),
        benchmark_name=require_field(payload, "benchmark_name"),
        kind=require_field(payload, "kind"),
    )
end


function instance_change_from_dict(payload::AbstractDict)
    allowed = Set(["instance_id", "problem_type", "benchmark_name", "metric_variant", "place_slug", "num_customers", "instance_name", "kind"])
    ensure_allowed_keys(payload, allowed, "InstanceChange")
    return InstanceChange(
        instance_id=require_field(payload, "instance_id"),
        problem_type=require_field(payload, "problem_type"),
        benchmark_name=require_field(payload, "benchmark_name"),
        metric_variant=get(payload, "metric_variant", nothing),
        place_slug=get(payload, "place_slug", nothing),
        num_customers=require_field(payload, "num_customers"),
        instance_name=require_field(payload, "instance_name"),
        kind=require_field(payload, "kind"),
    )
end


function bks_change_from_dict(payload::AbstractDict)
    allowed = Set(["instance_id", "problem_type", "benchmark_name", "metric_variant", "place_slug", "num_customers", "instance_name", "objective_function", "kind", "prev", "new", "cost_delta", "cost_pct", "routes_delta", "routes_pct"])
    ensure_allowed_keys(payload, allowed, "BksChange")
    return BksChange(
        instance_id=require_field(payload, "instance_id"),
        problem_type=require_field(payload, "problem_type"),
        benchmark_name=require_field(payload, "benchmark_name"),
        metric_variant=get(payload, "metric_variant", nothing),
        place_slug=get(payload, "place_slug", nothing),
        num_customers=require_field(payload, "num_customers"),
        instance_name=require_field(payload, "instance_name"),
        objective_function=require_field(payload, "objective_function"),
        kind=require_field(payload, "kind"),
        prev=get(payload, "prev", nothing),
        new=get(payload, "new", nothing),
        cost_delta=get(payload, "cost_delta", nothing),
        cost_pct=get(payload, "cost_pct", nothing),
        routes_delta=get(payload, "routes_delta", nothing),
        routes_pct=get(payload, "routes_pct", nothing),
    )
end


function change_counts_from_dict(payload::AbstractDict)
    allowed = Set(["families_added", "families_removed", "instances_added", "instances_removed", "bks_added", "bks_removed", "bks_improved", "bks_regressed"])
    ensure_allowed_keys(payload, allowed, "ChangeCounts")
    return ChangeCounts(
        families_added=get(payload, "families_added", 0),
        families_removed=get(payload, "families_removed", 0),
        instances_added=get(payload, "instances_added", 0),
        instances_removed=get(payload, "instances_removed", 0),
        bks_added=get(payload, "bks_added", 0),
        bks_removed=get(payload, "bks_removed", 0),
        bks_improved=get(payload, "bks_improved", 0),
        bks_regressed=get(payload, "bks_regressed", 0),
    )
end


function snapshot_change_log_from_dict(payload::AbstractDict)
    allowed = Set(["is_initial", "counts", "family_changes", "instance_changes", "bks_changes"])
    ensure_allowed_keys(payload, allowed, "SnapshotChangeLog")
    return SnapshotChangeLog(
        is_initial=require_field(payload, "is_initial"),
        counts=require_field(payload, "counts"),
        family_changes=get(payload, "family_changes", Any[]),
        instance_changes=get(payload, "instance_changes", Any[]),
        bks_changes=get(payload, "bks_changes", Any[]),
    )
end


function site_history_entry_from_dict(payload::AbstractDict)
    allowed = Set(["snapshot", "summary", "detail_route_path", "affected_problem_types", "affected_benchmark_names", "affected_objective_functions", "change_counts"])
    ensure_allowed_keys(payload, allowed, "SiteHistoryEntry")
    return SiteHistoryEntry(
        snapshot=require_field(payload, "snapshot"),
        summary=require_field(payload, "summary"),
        detail_route_path=require_field(payload, "detail_route_path"),
        affected_problem_types=get(payload, "affected_problem_types", String[]),
        affected_benchmark_names=get(payload, "affected_benchmark_names", String[]),
        affected_objective_functions=get(payload, "affected_objective_functions", String[]),
        change_counts=get(payload, "change_counts", Dict{String,Any}()),
    )
end


function site_history_ledger_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "current_snapshot_id", "entries"])
    ensure_allowed_keys(payload, allowed, "SiteHistoryLedger")
    return SiteHistoryLedger(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        current_snapshot_id=require_field(payload, "current_snapshot_id"),
        entries=require_field(payload, "entries"),
    )
end


function home_page_payload_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "route_path", "title", "subtitle", "hero_summary", "latest_publication_summary", "counts", "problems", "benchmarks_route_path", "project_route_path", "objectives_route_path", "history_route_path", "workbench_route_path"])
    ensure_allowed_keys(payload, allowed, "HomePagePayload")
    return HomePagePayload(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        route_path=get(payload, "route_path", "/"),
        title=require_field(payload, "title"),
        subtitle=require_field(payload, "subtitle"),
        hero_summary=require_field(payload, "hero_summary"),
        latest_publication_summary=require_field(payload, "latest_publication_summary"),
        counts=require_field(payload, "counts"),
        problems=require_field(payload, "problems"),
        benchmarks_route_path=get(payload, "benchmarks_route_path", "/benchmarks/"),
        project_route_path=get(payload, "project_route_path", "/project/"),
        objectives_route_path=get(payload, "objectives_route_path", "/objectives/"),
        history_route_path=get(payload, "history_route_path", "/history/"),
        workbench_route_path=get(payload, "workbench_route_path", "/workbench/"),
    )
end


function project_fact_from_dict(payload::AbstractDict)
    allowed = Set(["label", "value", "href"])
    ensure_allowed_keys(payload, allowed, "ProjectFact")
    return ProjectFact(
        label=require_field(payload, "label"),
        value=require_field(payload, "value"),
        href=get(payload, "href", nothing),
    )
end


function project_narrative_block_from_dict(payload::AbstractDict)
    allowed = Set(["title", "body", "tags"])
    ensure_allowed_keys(payload, allowed, "ProjectNarrativeBlock")
    return ProjectNarrativeBlock(
        title=require_field(payload, "title"),
        body=require_field(payload, "body"),
        tags=get(payload, "tags", String[]),
    )
end


function project_page_payload_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "route_path", "title", "subtitle", "breadcrumbs", "anr_project_code", "anr_project_url", "anr_project_title", "anr_context", "facts", "research_threads", "collaboration_note"])
    ensure_allowed_keys(payload, allowed, "ProjectPagePayload")
    return ProjectPagePayload(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        route_path=get(payload, "route_path", "/project/"),
        title=require_field(payload, "title"),
        subtitle=require_field(payload, "subtitle"),
        breadcrumbs=require_field(payload, "breadcrumbs"),
        anr_project_code=require_field(payload, "anr_project_code"),
        anr_project_url=require_field(payload, "anr_project_url"),
        anr_project_title=require_field(payload, "anr_project_title"),
        anr_context=require_field(payload, "anr_context"),
        facts=require_field(payload, "facts"),
        research_threads=require_field(payload, "research_threads"),
        collaboration_note=require_field(payload, "collaboration_note"),
    )
end


function history_detail_payload_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "route_path", "title", "breadcrumbs", "summary", "counts", "benchmark_index_path", "history_path", "affected_problem_types", "affected_benchmark_names", "affected_objective_functions", "change_log"])
    ensure_allowed_keys(payload, allowed, "HistoryDetailPayload")
    return HistoryDetailPayload(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        route_path=require_field(payload, "route_path"),
        title=require_field(payload, "title"),
        breadcrumbs=require_field(payload, "breadcrumbs"),
        summary=require_field(payload, "summary"),
        counts=require_field(payload, "counts"),
        benchmark_index_path=require_field(payload, "benchmark_index_path"),
        history_path=require_field(payload, "history_path"),
        affected_problem_types=get(payload, "affected_problem_types", String[]),
        affected_benchmark_names=get(payload, "affected_benchmark_names", String[]),
        affected_objective_functions=get(payload, "affected_objective_functions", String[]),
        change_log=require_field(payload, "change_log"),
    )
end


function benchmarks_index_payload_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "route_path", "breadcrumbs", "problems"])
    ensure_allowed_keys(payload, allowed, "BenchmarksIndexPayload")
    return BenchmarksIndexPayload(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        route_path=require_field(payload, "route_path"),
        breadcrumbs=get(payload, "breadcrumbs", BreadcrumbItem[BreadcrumbItem("benchmarks", "/benchmarks/")]),
        problems=require_field(payload, "problems"),
    )
end


function problem_index_payload_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "route_path", "title", "breadcrumbs", "problem_type", "summary", "families"])
    ensure_allowed_keys(payload, allowed, "ProblemIndexPayload")
    return ProblemIndexPayload(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        route_path=require_field(payload, "route_path"),
        title=require_field(payload, "title"),
        breadcrumbs=require_field(payload, "breadcrumbs"),
        problem_type=require_field(payload, "problem_type"),
        summary=require_field(payload, "summary"),
        families=require_field(payload, "families"),
    )
end


function catalog_index_payload_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "route_path", "title", "description", "breadcrumbs", "problem_type", "benchmark_name", "metric_variant", "place_slug", "size_bucket", "summary", "filter_facets", "variant_routes", "place_routes", "size_routes", "items"])
    ensure_allowed_keys(payload, allowed, "CatalogIndexPayload")
    return CatalogIndexPayload(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        route_path=require_field(payload, "route_path"),
        title=require_field(payload, "title"),
        description=get(payload, "description", nothing),
        breadcrumbs=require_field(payload, "breadcrumbs"),
        problem_type=require_field(payload, "problem_type"),
        benchmark_name=require_field(payload, "benchmark_name"),
        metric_variant=get(payload, "metric_variant", nothing),
        place_slug=get(payload, "place_slug", nothing),
        size_bucket=get(payload, "size_bucket", nothing),
        summary=require_field(payload, "summary"),
        filter_facets=get(payload, "filter_facets", FilterFacet[]),
        variant_routes=get(payload, "variant_routes", SubrouteEntry[]),
        place_routes=get(payload, "place_routes", SubrouteEntry[]),
        size_routes=get(payload, "size_routes", SubrouteEntry[]),
        items=get(payload, "items", InstanceListItem[]),
    )
end


function instance_page_payload_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "route_path", "title", "breadcrumbs", "locator", "summary", "artifact_links", "sibling_variant_routes", "derived_problem_routes", "source_problem_routes", "bks_entries", "workbench_route_path"])
    ensure_allowed_keys(payload, allowed, "InstancePagePayload")
    return InstancePagePayload(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        route_path=require_field(payload, "route_path"),
        title=require_field(payload, "title"),
        breadcrumbs=require_field(payload, "breadcrumbs"),
        locator=require_field(payload, "locator"),
        summary=require_field(payload, "summary"),
        artifact_links=require_field(payload, "artifact_links"),
        sibling_variant_routes=get(payload, "sibling_variant_routes", Dict{String,String}()),
        derived_problem_routes=get(payload, "derived_problem_routes", Dict{String,String}()),
        source_problem_routes=get(payload, "source_problem_routes", Dict{String,String}()),
        bks_entries=get(payload, "bks_entries", BKSPageEntry[]),
        workbench_route_path=get(payload, "workbench_route_path", "/workbench/"),
    )
end


function objectives_page_payload_from_dict(payload::AbstractDict)
    allowed = Set(["payload_kind", "schema_version", "generated_at", "snapshot", "route_path", "title", "breadcrumbs", "explainers"])
    ensure_allowed_keys(payload, allowed, "ObjectivesPagePayload")
    return ObjectivesPagePayload(
        payload_kind=require_field(payload, "payload_kind"),
        schema_version=require_field(payload, "schema_version"),
        generated_at=require_field(payload, "generated_at"),
        snapshot=require_field(payload, "snapshot"),
        route_path=require_field(payload, "route_path"),
        title=require_field(payload, "title"),
        breadcrumbs=require_field(payload, "breadcrumbs"),
        explainers=require_field(payload, "explainers"),
    )
end


function site_payload_from_dict(payload::AbstractDict)
    payload_kind = require_choice(coerce_string(require_field(payload, "payload_kind"), "payload_kind"), SITE_PAYLOAD_KINDS, "payload_kind")
    if payload_kind == "home_page"
        return home_page_payload_from_dict(payload)
    end
    if payload_kind == "site_snapshot"
        return site_snapshot_manifest_from_dict(payload)
    end
    if payload_kind == "site_history"
        return site_history_ledger_from_dict(payload)
    end
    if payload_kind == "history_detail"
        return history_detail_payload_from_dict(payload)
    end
    if payload_kind == "project_page"
        return project_page_payload_from_dict(payload)
    end
    if payload_kind == "benchmarks_index"
        return benchmarks_index_payload_from_dict(payload)
    end
    if payload_kind == "problem_index"
        return problem_index_payload_from_dict(payload)
    end
    if payload_kind in CATALOG_PAYLOAD_KINDS
        return catalog_index_payload_from_dict(payload)
    end
    if payload_kind == "instance_page"
        return instance_page_payload_from_dict(payload)
    end
    if payload_kind == "objectives_page"
        return objectives_page_payload_from_dict(payload)
    end
    error("Unsupported site payload kind '$payload_kind'")
end


function model_from_dict(payload::AbstractDict; migrate_legacy::Bool=true)
    if haskey(payload, "payload_kind")
        return site_payload_from_dict(payload)
    end

    if haskey(payload, "objective_function")
        return benchmark_bks_from_dict(payload)
    end

    if haskey(payload, "instance_id") && haskey(payload, "metadata")
        metadata_payload = require_field(payload, "metadata")
        metadata_payload isa AbstractDict || error("metadata must be an object")
        problem_type = get(metadata_payload, "problem_type", nothing)
        if problem_type == "CVRP"
            return benchmark_instance_cvrp_from_dict(payload)
        end
        if problem_type == "VRPTW"
            return benchmark_instance_vrptw_from_dict(payload)
        end
        haskey(payload, "service_times") && return benchmark_instance_vrptw_from_dict(payload)
        return benchmark_instance_cvrp_from_dict(payload)
    end

    if haskey(payload, "instance_name")
        if haskey(payload, "arc_costs")
            return historical_benchmark_instance_from_dict(payload)
        end
        migrate_legacy || error("JSON payload is missing 'arc_costs'")
        return historical_benchmark_instance_from_legacy_dict(payload)
    end

    return Dict{String,Any}(String(key) => value for (key, value) in pairs(payload))
end


function load_json_model(filepath::AbstractString; migrate_legacy::Bool=true)
    payload = load_json_from_file(filepath)
    payload isa AbstractDict || error("JSON payload must decode to an object")
    return model_from_dict(payload; migrate_legacy=migrate_legacy)
end


function is_site_payload_model(model)
    return model isa SiteSnapshotManifest ||
           model isa SiteHistoryLedger ||
           model isa HomePagePayload ||
           model isa ProjectPagePayload ||
           model isa HistoryDetailPayload ||
           model isa BenchmarksIndexPayload ||
           model isa ProblemIndexPayload ||
           model isa CatalogIndexPayload ||
           model isa InstancePagePayload ||
           model isa ObjectivesPagePayload
end


function load_json_site_payload(filepath::AbstractString)
    model = load_json_model(filepath)
    is_site_payload_model(model) || error("JSON payload at $filepath is not a site payload")
    return model
end


function write_json_model(value, filepath::AbstractString; indent::Int=4, sort_keys::Bool=false)
    serializable = value isa AbstractDict ? value : payload(value)
    return save_json_to_file(serializable, filepath; indent=indent, sort_keys=sort_keys)
end


function write_json_site_payload(value, filepath::AbstractString; indent::Int=4, sort_keys::Bool=false)
    is_site_payload_model(value) || error("Value is not a site payload model")
    return write_json_model(value, filepath; indent=indent, sort_keys=sort_keys)
end


function load_json_instance(filepath::AbstractString; migrate_legacy::Bool=true)
    model = load_json_model(filepath; migrate_legacy=migrate_legacy)
    model isa HistoricalBenchmarkInstance || error("JSON instance at $filepath is not a historical benchmark instance")
    return model
end


function write_json_instance(instance::HistoricalBenchmarkInstance, filepath::AbstractString; indent::Int=4, sort_keys::Bool=false)
    return write_json_model(instance, filepath; indent=indent, sort_keys=sort_keys)
end


function parse_header_line(line::AbstractString)
    matched = match(r"^([A-Z_]+)\s*:\s*(.+)$", strip(line))
    matched === nothing && return nothing
    return (String(matched.captures[1]), String(strip(matched.captures[2])))
end


function parse_vrp_sections(vrp_text::AbstractString)
    headers = Dict{String,String}()
    sections = Dict{String,Vector{String}}()
    current_section = nothing

    for raw_line in split(vrp_text, '\n')
        stripped = strip(raw_line)
        isempty(stripped) && continue

        uppercase_line = uppercase(stripped)
        if uppercase_line == "EOF"
            current_section = nothing
            continue
        end

        if uppercase_line in KNOWN_VRP_SECTIONS
            current_section = uppercase_line
            sections[current_section] = String[]
            continue
        end

        if current_section !== nothing
            push!(sections[current_section], stripped)
            continue
        end

        header = parse_header_line(stripped)
        header === nothing && error("Could not parse VRP line '$stripped'")
        headers[header[1]] = header[2]
    end

    return headers, sections
end


function header_value(headers::AbstractDict, key::AbstractString)
    haskey(headers, key) || error("Missing $key header in VRP text")
    return headers[key]
end


function section_lines(sections::AbstractDict, key::AbstractString; required::Bool=true)
    if haskey(sections, key)
        return sections[key]
    end
    required && error("Missing $key section in VRP text")
    return String[]
end


function parse_scalar(token::AbstractString)
    int_value = tryparse(Int, token)
    int_value !== nothing && return int_value
    float_value = tryparse(Float64, token)
    float_value !== nothing && return float_value
    error("Could not parse numeric value '$token'")
end


function parse_matrix_section(lines::Vector{String}, dimension::Int)
    tokens = String[]
    for line in lines
        append!(tokens, split(line))
    end
    expected = dimension * dimension
    length(tokens) == expected || error("EDGE_WEIGHT_SECTION has $(length(tokens)) values, expected $expected")

    parsed = [parse_scalar(token) for token in tokens]
    if all(is_integral_number, parsed)
        rows = Vector{Vector{Int}}(undef, dimension)
        for row_index in 1:dimension
            start_index = (row_index - 1) * dimension + 1
            rows[row_index] = [coerce_int(parsed[index], "arc_costs") for index in start_index:(start_index + dimension - 1)]
        end
        return rows
    end

    rows = Vector{Vector{Float64}}(undef, dimension)
    for row_index in 1:dimension
        start_index = (row_index - 1) * dimension + 1
        rows[row_index] = [coerce_real(parsed[index], "arc_costs") for index in start_index:(start_index + dimension - 1)]
    end
    return rows
end


function parse_node_coords_section(lines::Vector{String}, dimension::Int)
    coordinates = Vector{NTuple{2,Float64}}(undef, dimension)
    seen = falses(dimension)
    for line in lines
        parts = split(line)
        length(parts) >= 3 || error("Invalid NODE_COORD_SECTION line: '$line'")
        node_index = parse(Int, parts[1])
        1 <= node_index <= dimension || error("NODE_COORD_SECTION index $node_index is out of bounds [1,$dimension]")
        coordinates[node_index] = (parse(Float64, parts[2]), parse(Float64, parts[3]))
        seen[node_index] = true
    end
    all(seen) || error("NODE_COORD_SECTION is missing one or more node coordinates")
    return coordinates
end


function parse_demands_section(lines::Vector{String}, dimension::Int)
    demands = Vector{Int}(undef, dimension)
    seen = falses(dimension)
    for line in lines
        parts = split(line)
        length(parts) >= 2 || error("Invalid DEMAND_SECTION line: '$line'")
        node_index = parse(Int, parts[1])
        1 <= node_index <= dimension || error("DEMAND_SECTION index $node_index is out of bounds [1,$dimension]")
        demands[node_index] = parse(Int, parts[2])
        seen[node_index] = true
    end
    all(seen) || error("DEMAND_SECTION is missing one or more node demands")
    return demands
end


function parse_depot_section(lines::Vector{String}, dimension::Int)
    depot_values = Int[]
    for line in lines
        for token in split(line)
            value = parse(Int, token)
            value == -1 && break
            push!(depot_values, value)
        end
        any(==( -1), parse.(Int, split(line))) && break
    end
    isempty(depot_values) && error("DEPOT_SECTION does not contain a depot node id")
    depot_index = depot_values[1]
    1 <= depot_index <= dimension || error("Depot node id $depot_index is out of bounds [1,$dimension]")
    return depot_index - 1
end


function parse_time_windows_section(lines::Vector{String}, dimension::Int)
    time_windows = Vector{NTuple{2,Int}}(undef, dimension)
    seen = falses(dimension)
    for line in lines
        parts = split(line)
        length(parts) >= 3 || error("Invalid TIME_WINDOW_SECTION line: '$line'")
        node_index = parse(Int, parts[1])
        1 <= node_index <= dimension || error("TIME_WINDOW_SECTION index $node_index is out of bounds [1,$dimension]")
        earliest = parse(Int, parts[2])
        latest = parse(Int, parts[3])
        earliest <= latest || error("TIME_WINDOW_SECTION earliest > latest for node $node_index")
        time_windows[node_index] = (earliest, latest)
        seen[node_index] = true
    end
    all(seen) || error("TIME_WINDOW_SECTION is missing one or more nodes")
    return time_windows
end


function parse_service_time_section(lines::Vector{String}, dimension::Int)
    service_times = Vector{Int}(undef, dimension)
    seen = falses(dimension)
    for line in lines
        parts = split(line)
        length(parts) >= 2 || error("Invalid SERVICE_TIME_SECTION line: '$line'")
        node_index = parse(Int, parts[1])
        1 <= node_index <= dimension || error("SERVICE_TIME_SECTION index $node_index is out of bounds [1,$dimension]")
        service_times[node_index] = parse(Int, parts[2])
        seen[node_index] = true
    end
    all(seen) || error("SERVICE_TIME_SECTION is missing one or more nodes")
    return service_times
end


function normalize_depot_first(
    matrix_rows,
    coordinates::Vector{NTuple{2,Float64}},
    demands::Vector{Int},
    depot::Int;
    service_times::Union{Nothing,Vector{Int}}=nothing,
    time_windows::Union{Nothing,Vector{NTuple{2,Int}}}=nothing,
)
    depot == 0 && return matrix_rows, coordinates, demands, service_times, time_windows

    dimension = length(demands)
    depot_one_based = depot + 1
    order = vcat([depot_one_based], [index for index in 1:dimension if index != depot_one_based])
    reordered_coordinates = coordinates[order]
    reordered_demands = demands[order]
    reordered_matrix = [[matrix_rows[old_row][old_col] for old_col in order] for old_row in order]
    reordered_service_times = service_times === nothing ? nothing : service_times[order]
    reordered_time_windows = time_windows === nothing ? nothing : time_windows[order]
    return reordered_matrix, reordered_coordinates, reordered_demands, reordered_service_times, reordered_time_windows
end


function parse_vrp_file(filepath::AbstractString)
    vrp_text = read(filepath, String)
    headers, sections = parse_vrp_sections(vrp_text)

    vrp_type = get(headers, "TYPE", "CVRP")
    vrp_type in VRP_TYPES || error("TYPE must be one of $(collect(VRP_TYPES))")
    name = header_value(headers, "NAME")
    dimension = parse(Int, header_value(headers, "DIMENSION"))
    dimension >= 2 || error("DIMENSION must be at least 2")
    capacity = parse(Int, header_value(headers, "CAPACITY"))
    capacity > 0 || error("CAPACITY must be positive")

    edge_weight_type = uppercase(get(headers, "EDGE_WEIGHT_TYPE", "EXPLICIT"))
    edge_weight_type == "EXPLICIT" || error("Only EDGE_WEIGHT_TYPE=EXPLICIT is supported")
    edge_weight_format = uppercase(get(headers, "EDGE_WEIGHT_FORMAT", "FULL_MATRIX"))
    edge_weight_format == "FULL_MATRIX" || error("Only EDGE_WEIGHT_FORMAT=FULL_MATRIX is supported")

    matrix_rows = parse_matrix_section(section_lines(sections, "EDGE_WEIGHT_SECTION"), dimension)
    coordinates = parse_node_coords_section(section_lines(sections, "NODE_COORD_SECTION"), dimension)
    demands = parse_demands_section(section_lines(sections, "DEMAND_SECTION"), dimension)
    depot = parse_depot_section(section_lines(sections, "DEPOT_SECTION"), dimension)

    service_times = nothing
    if haskey(sections, "SERVICE_TIME_SECTION")
        service_times = parse_service_time_section(section_lines(sections, "SERVICE_TIME_SECTION"), dimension)
    elseif haskey(headers, "SERVICE_TIME")
        customer_service_time = parse(Int, headers["SERVICE_TIME"])
        service_times = vcat([0], fill(customer_service_time, dimension - 1))
    end

    time_windows = haskey(sections, "TIME_WINDOW_SECTION") ? parse_time_windows_section(section_lines(sections, "TIME_WINDOW_SECTION"), dimension) : nothing

    matrix_rows, coordinates, demands, service_times, time_windows = normalize_depot_first(
        matrix_rows,
        coordinates,
        demands,
        depot;
        service_times=service_times,
        time_windows=time_windows,
    )

    return ParsedVrpInstance(
        name=name,
        vrp_type=vrp_type,
        comment=get(headers, "COMMENT", nothing),
        dimension=dimension,
        capacity=capacity,
        arc_costs=matrix_rows,
        coordinates=coordinates,
        demands=demands,
        depot=0,
        service_times=service_times,
        time_windows=time_windows,
    )
end


function vrp_number_string(value::Real)
    return is_integral_number(value) ? string(round(Int, value)) : string(value)
end


function write_vrp_string(
    parsed::ParsedVrpInstance;
    comment::Union{Nothing,AbstractString}=parsed.comment,
)
    lines = String[]
    push!(lines, "NAME : $(parsed.name)")
    push!(lines, "TYPE : $(parsed.vrp_type)")
    comment === nothing || push!(lines, "COMMENT : $comment")
    push!(lines, "DIMENSION : $(parsed.dimension)")
    push!(lines, "CAPACITY : $(parsed.capacity)")
    push!(lines, "EDGE_WEIGHT_TYPE : EXPLICIT")
    push!(lines, "EDGE_WEIGHT_FORMAT : FULL_MATRIX")
    push!(lines, "EDGE_WEIGHT_SECTION")
    for row in parsed.arc_costs
        push!(lines, join((vrp_number_string(value) for value in row), " "))
    end
    push!(lines, "NODE_COORD_SECTION")
    for (index, (x_coord, y_coord)) in enumerate(parsed.coordinates)
        push!(lines, "$index $(vrp_number_string(x_coord)) $(vrp_number_string(y_coord))")
    end
    push!(lines, "DEMAND_SECTION")
    for (index, demand) in enumerate(parsed.demands)
        push!(lines, "$index $demand")
    end
    if parsed.time_windows !== nothing
        push!(lines, "TIME_WINDOW_SECTION")
        for (index, (ready_time, due_date)) in enumerate(parsed.time_windows)
            push!(lines, "$index $ready_time $due_date")
        end
    end
    if parsed.service_times !== nothing
        push!(lines, "SERVICE_TIME_SECTION")
        for (index, service_time) in enumerate(parsed.service_times)
            push!(lines, "$index $service_time")
        end
    end
    push!(lines, "DEPOT_SECTION")
    push!(lines, string(parsed.depot + 1))
    push!(lines, "-1")
    push!(lines, "EOF")
    return join(lines, "\n") * "\n"
end


function write_vrp_file(
    parsed::ParsedVrpInstance,
    filepath::AbstractString;
    comment::Union{Nothing,AbstractString}=parsed.comment,
)
    mkpath(dirname(filepath))
    open(filepath, "w") do io
        write(io, write_vrp_string(parsed; comment=comment))
    end
    return filepath
end


function parsed_vrp_from_historical_instance(
    instance::HistoricalBenchmarkInstance;
    comment::AbstractString="Generated from HistoricalBenchmarkInstance JSON",
)
    return ParsedVrpInstance(
        name=instance.instance_name,
        vrp_type="CVRPTW",
        comment=comment,
        dimension=instance.num_customers + 1,
        capacity=instance.vehicle_capacity,
        arc_costs=instance.arc_costs,
        coordinates=instance.coordinates,
        demands=instance.demands,
        depot=instance.depot,
        service_times=instance.service_times,
        time_windows=instance.time_windows,
    )
end


function parsed_vrp_from_cvrp_instance(
    instance::BenchmarkInstanceCVRP;
    comment::AbstractString="Generated from BenchmarkInstanceCVRP JSON",
)
    return ParsedVrpInstance(
        name=instance.instance_id,
        vrp_type="CVRP",
        comment=comment,
        dimension=instance.num_customers + 1,
        capacity=instance.vehicle_capacity,
        arc_costs=instance.arc_costs,
        coordinates=instance.coordinates,
        demands=instance.demands,
        depot=instance.depot,
        service_times=nothing,
        time_windows=nothing,
    )
end


function parsed_vrp_from_vrptw_instance(
    instance::BenchmarkInstanceVRPTW;
    comment::AbstractString="Generated from BenchmarkInstanceVRPTW JSON",
)
    return ParsedVrpInstance(
        name=instance.instance_id,
        vrp_type="CVRPTW",
        comment=comment,
        dimension=instance.num_customers + 1,
        capacity=instance.vehicle_capacity,
        arc_costs=instance.arc_costs,
        coordinates=instance.coordinates,
        demands=instance.demands,
        depot=instance.depot,
        service_times=instance.service_times,
        time_windows=instance.time_windows,
    )
end


function write_vrp_file(
    instance::HistoricalBenchmarkInstance,
    filepath::AbstractString;
    comment::AbstractString="Generated from HistoricalBenchmarkInstance JSON",
)
    return write_vrp_file(parsed_vrp_from_historical_instance(instance; comment=comment), filepath; comment=comment)
end


function write_vrp_file(
    instance::BenchmarkInstanceCVRP,
    filepath::AbstractString;
    comment::AbstractString="Generated from BenchmarkInstanceCVRP JSON",
)
    return write_vrp_file(parsed_vrp_from_cvrp_instance(instance; comment=comment), filepath; comment=comment)
end


function write_vrp_file(
    instance::BenchmarkInstanceVRPTW,
    filepath::AbstractString;
    comment::AbstractString="Generated from BenchmarkInstanceVRPTW JSON",
)
    return write_vrp_file(parsed_vrp_from_vrptw_instance(instance; comment=comment), filepath; comment=comment)
end
