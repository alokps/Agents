from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from .helper_utils import base_url, api_key

@CrewBase
class Debate():
    """Debate crew"""


    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    llm_instance = LLM(
            base_url=base_url,
            api_key=api_key,
            model="gpt-5"
        )

    @agent
    def debater(self) -> Agent:
        # Create LLM instance directly instead of using string from config
        
        self.llm_instance.model = "gpt-5-mini"
        
        return Agent(
            config=self.agents_config['debater'],
            llm=self.llm_instance,
            verbose=True
        )

    @agent
    def judge(self) -> Agent:
        # Create LLM instance directly instead of using string from config
        
        self.llm_instance.model = "gpt-5"
        
        return Agent(
            config=self.agents_config['judge'],
            llm=self.llm_instance,
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
