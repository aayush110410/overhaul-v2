import pytest
from engines.agent_simulation.swarm import SwarmResult
from engines.agent_simulation.ldrago_parser import LDRAGOParser, ParsedSimulationBrief

def test_parse_extracts_metrics():
    # Setup
    result = SwarmResult(
        avg_speed_kmh=25.5,
        congestion_pct=42.0,
        total_pm25_g=5000.0,  # 5kg
        total_co2_kg=1000000.0, # 1000 tonnes
        total_mode_shifts=150
    )
    parser = LDRAGOParser()
    brief = parser.parse(result)

    assert brief.avg_speed_kmh == 25.5
    assert brief.congestion_pct == 42.0
    assert brief.pm25_kg == 5.0
    assert brief.co2_tonnes == 1000.0
    assert brief.mode_shift_count == 150

def test_generate_markdown():
    parser = LDRAGOParser()
    brief = ParsedSimulationBrief(
        avg_speed_kmh=20.0,
        congestion_pct=30.0,
        pm25_kg=2.0,
        co2_tonnes=500.0,
        emergent_hotspots=[],
        mode_shift_count=10
    )
    markdown = parser.generate_markdown(brief)

    assert "Average Speed" in markdown
    assert "Congestion" in markdown
    assert "20.0" in markdown
    assert "30.0%" in markdown

def test_extracts_hotspots_and_mode_shifts():
    result = SwarmResult(
        hotspots=[
            {"edge": "A->B", "congestion_ratio": 0.9},
            {"edge": "C->D", "congestion_ratio": 0.85}
        ],
        total_mode_shifts=42
    )
    parser = LDRAGOParser()
    brief = parser.parse(result)

    assert len(brief.emergent_hotspots) == 2
    assert brief.emergent_hotspots[0]["edge"] == "A->B"
    assert brief.mode_shift_count == 42
