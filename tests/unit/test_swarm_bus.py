from metis.swarm.bus import SwarmBus


def test_swarm_bus_collects_agent_results():
    bus = SwarmBus()
    bus.register_agent("explorer-1")
    bus.publish("explorer-1", {"summary": "found files"})

    assert bus.collect("explorer-1")[0].payload["summary"] == "found files"
    assert len(bus.collect()) == 1
