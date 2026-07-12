"""
core/transport.py

Mock "getting to the stadium" transit data and sustainability scoring.

WHY THIS EXISTS:
Two of the PromptWars brief's eight named themes - transportation and
sustainability - weren't touched by the original build, which focused
entirely on navigation *inside* the venue (core/routing.py). This module
is deliberately scoped as "day-of transit options a fan compares before
they even enter a gate" (metro / bus / shuttle-from-parking / driving),
reusing the same gates and Parking_Lot node already defined in
core/venue.py rather than bolting on a second, disconnected data model.

In a real deployment this would be a live transit API (GTFS feeds, a city
transit API, or a rideshare partner's ETA endpoint). For this MVP it's
hardcoded mock data - same spirit as CrowdSimulator standing in for real
sensors elsewhere in this project.

SUSTAINABILITY NOTE: the per-km CO2 figures below are widely-cited rough
averages (metro/bus/car relative ordering is well established; shuttle is
estimated as a shared, shorter-hop variant of bus), not this venue's
actual measured footprint. They're good enough for a *relative* "this
option is measurably greener than driving alone" comparison - not a
compliance-grade emissions audit.
"""

from __future__ import annotations  # allows `list[TransitOption]` etc. on Python < 3.10

from dataclasses import dataclass
from typing import TypedDict


class _TransitLegInfo(TypedDict):
    """One gate's nearest metro or bus leg: a name plus walk/ride times."""

    label_name: str
    walk_minutes: int
    ride_minutes: int


class _ShuttleInfo(TypedDict):
    label_name: str
    wait_minutes: int
    ride_minutes: int


class _CarInfo(TypedDict):
    label_name: str
    walk_minutes: int
    ride_minutes: int


# Documented assumption: the average one-way distance a fan travels to
# reach the stadium. Used only to turn a per-km emissions rate into a
# concrete per-trip number for the demo - not a claim about any specific
# fan's actual commute.
AVG_TRIP_KM = 8.0

# Rough, widely-cited average grams of CO2 per passenger-km. Precision
# isn't the point - the ordering is: metro < shuttle < bus < solo car,
# which holds across most published transit-emissions comparisons.
CO2_GRAMS_PER_KM: dict[str, int] = {
    "metro": 41,
    "shuttle": 68,
    "bus": 105,
    "car": 192,
}

# Per-gate options: each of the three gates has its own nearest metro stop
# and bus route (distinct walk/ride times), mirroring how a real fan's
# "best" option genuinely depends on which gate they're headed to.
GATE_TRANSIT_OPTIONS: dict[str, dict[str, _TransitLegInfo]] = {
    "Gate_A": {
        "metro": {"label_name": "Central Stadium Metro (Blue Line)", "walk_minutes": 6, "ride_minutes": 18},
        "bus": {"label_name": "Route 42 (Stadium North Stop)", "walk_minutes": 4, "ride_minutes": 25},
    },
    "Gate_B": {
        "metro": {"label_name": "West Concourse Metro (Green Line)", "walk_minutes": 9, "ride_minutes": 15},
        "bus": {"label_name": "Route 17 (West Gate Stop)", "walk_minutes": 3, "ride_minutes": 22},
    },
    "Gate_C": {
        "metro": {"label_name": "East Plaza Metro (Red Line)", "walk_minutes": 12, "ride_minutes": 20},
        "bus": {"label_name": "Route 8 (East Gate Stop)", "walk_minutes": 5, "ride_minutes": 28},
    },
}

# The shuttle runs from the shared Parking_Lot node (core/venue.py) to
# every gate - this is the one option every gate has in common, since it's
# physically the same lot. Same for driving yourself: every gate's fans
# who drove end up parking at the same Parking_Lot.
SHUTTLE_INFO: _ShuttleInfo = {"label_name": "Free shuttle from Parking_Lot", "wait_minutes": 8, "ride_minutes": 6}
CAR_INFO: _CarInfo = {"label_name": "Drive & park at Parking_Lot", "walk_minutes": 3, "ride_minutes": 0}


@dataclass
class TransitOption:
    """One way to reach a gate, with a rough time and emissions estimate."""

    mode: str  # "metro" | "bus" | "shuttle" | "car"
    label: str  # human-readable description, for display and LLM prompts
    total_minutes: int
    co2_grams: float
    co2_saved_vs_car_grams: float


def _co2_for_mode(mode: str, distance_km: float = AVG_TRIP_KM) -> float:
    """Grams of CO2 for one passenger traveling distance_km by the given mode."""
    rate = CO2_GRAMS_PER_KM.get(mode, CO2_GRAMS_PER_KM["car"])
    return rate * distance_km


def get_transit_options(gate: str, distance_km: float = AVG_TRIP_KM) -> list[TransitOption]:
    """
    Build the list of transit options for reaching a given gate.

    Every gate gets its own nearest metro + bus (from GATE_TRANSIT_OPTIONS),
    plus the shared shuttle-from-parking and drive-yourself options that
    apply everywhere. An unrecognized gate name still gets shuttle + car
    (the two options that don't depend on gate-specific transit lines),
    rather than an empty list or an error.

    Args:
        gate: gate node name, e.g. "Gate_A"
        distance_km: assumed one-way trip distance, for the CO2 math

    Returns:
        List of TransitOption, in a fixed, deterministic order
        (metro, bus, shuttle, car - whichever apply).
    """
    car_emission = _co2_for_mode("car", distance_km)
    options: list[TransitOption] = []

    gate_specific = GATE_TRANSIT_OPTIONS.get(gate, {})
    for mode in ("metro", "bus"):
        info = gate_specific.get(mode)
        if not info:
            continue
        emission = _co2_for_mode(mode, distance_km)
        options.append(
            TransitOption(
                mode=mode,
                label=f"{info['label_name']} ({info['walk_minutes']} min walk + {info['ride_minutes']} min ride)",
                total_minutes=info["walk_minutes"] + info["ride_minutes"],
                co2_grams=emission,
                co2_saved_vs_car_grams=max(0.0, car_emission - emission),
            )
        )

    shuttle_emission = _co2_for_mode("shuttle", distance_km)
    options.append(
        TransitOption(
            mode="shuttle",
            label=(
                f"{SHUTTLE_INFO['label_name']} "
                f"({SHUTTLE_INFO['wait_minutes']} min wait + {SHUTTLE_INFO['ride_minutes']} min ride)"
            ),
            total_minutes=SHUTTLE_INFO["wait_minutes"] + SHUTTLE_INFO["ride_minutes"],
            co2_grams=shuttle_emission,
            co2_saved_vs_car_grams=max(0.0, car_emission - shuttle_emission),
        )
    )

    options.append(
        TransitOption(
            mode="car",
            label=CAR_INFO["label_name"],
            total_minutes=CAR_INFO["walk_minutes"] + CAR_INFO["ride_minutes"],
            co2_grams=car_emission,
            co2_saved_vs_car_grams=0.0,
        )
    )

    return options


def recommend_greenest_option(options: list[TransitOption]) -> TransitOption:
    """
    Pick the lowest-emission option. Ties broken by shortest total_minutes,
    so the recommendation stays sensible in the edge case where two modes
    end up with equal CO2.
    """
    return min(options, key=lambda o: (o.co2_grams, o.total_minutes))


if __name__ == "__main__":
    # Quick manual check: python core/transport.py
    for gate_name in ("Gate_A", "Gate_B", "Gate_C", "Unknown_Gate"):
        opts = get_transit_options(gate_name)
        best = recommend_greenest_option(opts)
        print(f"\n{gate_name}:")
        for opt in opts:
            print(f"  {opt.mode}: {opt.label} - {opt.total_minutes} min, {opt.co2_grams:.0f}g CO2")
        print(f"  -> Recommended: {best.mode} (saves {best.co2_saved_vs_car_grams:.0f}g CO2 vs car)")
