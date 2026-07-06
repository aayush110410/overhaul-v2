import pytest
from unittest.mock import MagicMock
from engines.agent_simulation.agents.report_agent import ReportAgent, ReportConfig

class MockSwarmResult:
    def __init__(self, congestion_pct=10, avg_speed_kmh=40, ev_share=0.2, total_vkt=1000, hotspots=None):
        self.congestion_pct = congestion_pct
        self.avg_speed_kmh = avg_speed_kmh
        self.ev_share = ev_share
        self.total_vkt = total_vkt
        self.hotspots = hotspots or []

class MockCollectiveTruth:
    def __init__(self, timestep=1, mood="neutral", confidence=0.8):
        self.timestep = timestep
        self.segment_mood = mood
        self.confidence = confidence
        self.preferred_routes = ["R1"]
        self.avoid_zones = ["Z1"]
        self.dissenting_signals = []
        self.stale = False

def test_report_agent_verdict_approve():
    mock_brains = {}
    agent = ReportAgent(segment_brains=mock_brains)
    result = MockSwarmResult(congestion_pct=10)

    verdict = agent.generate_verdict(result)
    assert verdict["verdict"] == "approve"

def test_report_agent_verdict_reject():
    mock_brains = {}
    agent = ReportAgent(segment_brains=mock_brains)
    result = MockSwarmResult(congestion_pct=50)

    verdict = agent.generate_verdict(result)
    assert verdict["verdict"] == "reject"

def test_collect_segment_insights():
    mock_brain = MagicMock()
    mock_brain.get_history.return_value = [MockCollectiveTruth(timestep=1), MockCollectiveTruth(timestep=2)]
    mock_brains = {"SegmentA": mock_brain}

    agent = ReportAgent(segment_brains=mock_brains)
    insights = agent.collect_segment_insights()

    assert "SegmentA" in insights
    assert len(insights["SegmentA"]) == 2
    assert insights["SegmentA"][1]["timestep"] == 2

def test_generate_summary_fallback():
    mock_brains = {}
    agent = ReportAgent(segment_brains=mock_brains, llm_provider=None)
    verdict = {"verdict": "approve", "confidence": 0.7, "key_metrics": {"congestion_pct": 10, "avg_speed_kmh": 40, "ev_share": 0.2}}
    insights = {"SegmentA": [{"mood": "happy", "confidence": 0.9}]}

    summary = agent.generate_summary(verdict, insights)
    assert "# Simulation Report" in summary
    assert "Verdict: APPROVE" in summary
    assert "SegmentA: happy" in summary

def test_generate_report_full():
    mock_brain = MagicMock()
    mock_brain.get_history.return_value = [MockCollectiveTruth()]
    mock_brains = {"SegmentA": mock_brain}

    agent = ReportAgent(segment_brains=mock_brains)
    swarm_result = MockSwarmResult(congestion_pct=45, avg_speed_kmh=15, ev_share=0.05)

    report = agent.generate_report(swarm_result)

    assert report.verdict["verdict"] == "reject"
    assert any("congestion pricing" in rec for rec in report.recommendations)
    assert any("EV incentives" in rec for rec in report.recommendations)
    assert any("signal timing" in rec for rec in report.recommendations)
    assert report.raw_metrics["congestion_pct"] == 45
