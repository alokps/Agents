from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from fordllm.utils import TokenFetcher


@CrewBase
class Debate():
    """Debate crew"""


    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    token_fetcher = TokenFetcher()
    base_url = "https://api.pivpn.core.ford.com/fordllmapi/api/v1"
    api_key = token_fetcher.token

    @agent
    def debater(self) -> Agent:
        # Create LLM instance directly instead of using string from config
        llm_instance = LLM(
            base_url=self.base_url,
            api_key=self.api_key,
            model="gpt-5-mini"
        )
        
        return Agent(
            config=self.agents_config['debater'],
            llm=llm_instance,
            verbose=True
        )

    @agent
    def judge(self) -> Agent:
        # Create LLM instance directly instead of using string from config
        llm_instance = LLM(
            base_url=self.base_url,
            api_key=self.api_key,
            model="gpt-5",
        )
        return Agent(
            config=self.agents_config['judge'],
            llm=llm_instance,
            verbose=True
        )

    @task
    def propose(self) -> Task:
        return Task(
            config=self.tasks_config['propose'],
        )

    @task
    def oppose(self) -> Task:
        return Task(
            config=self.tasks_config['oppose'],
        )

    @task
    def decide(self) -> Task:
        return Task(
            config=self.tasks_config['decide'],
        )


    @crew
    def crew(self) -> Crew:
        """Creates the Debate crew"""

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            tracing=True # Enables tracing for debugging purposes and stores
                         # trace data here: https://app.crewai.com/crewai_plus/ephemeral_trace_batches
        )
