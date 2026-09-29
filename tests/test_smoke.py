from agents import Agent


def test_agent_creation() -> None:
    agent = Agent(
        name="TestAgent",
        instructions="Test agent.",
    )

    assert agent.name == "TestAgent"
